#!/usr/bin/python3
import http.server
import io
import threading
import unittest
from unittest import mock

import httpx

from pysalesforceutils import webservice

URL = 'https://example.my.salesforce.com/services/data/'


class TestWebservice(unittest.TestCase):
    """
    These tests send requests through httpx to a handler function instead of
    the network, so they check the request that would really be sent.
    """

    def setUp(self):
        self.requests = []
        self.response = httpx.Response(200, json={'ok': True})

        def handler(request):
            request.read()
            self.requests.append(request)
            return self.response

        patcher = mock.patch.object(webservice.Tools, 'client', httpx.Client(transport=httpx.MockTransport(handler)))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_http_request_returns_response(self):
        response = webservice.Tools.get_http_response(URL, {'Accept': 'application/json'})

        self.assertEqual(response.json(), {'ok': True})
        self.assertEqual(self.requests[0].method, 'GET')
        self.assertEqual(str(self.requests[0].url), URL)
        self.assertEqual(self.requests[0].headers['Accept'], 'application/json')

    def test_http_request_uses_default_timeout(self):
        webservice.Tools.get_http_response(URL, {})

        self.assertEqual(webservice.Tools.default_timeout, 120)
        self.assertEqual(self.requests[0].extensions['timeout'],
                         {'connect': 120, 'read': 120, 'write': 120, 'pool': 120})

    def test_timeout_can_be_turned_off(self):
        with mock.patch.object(webservice.Tools, 'default_timeout', None):
            webservice.Tools.get_http_response(URL, {})

        self.assertEqual(self.requests[0].extensions['timeout'],
                         {'connect': None, 'read': None, 'write': None, 'pool': None})

    def test_json_error_keeps_body_and_response(self):
        self.response = httpx.Response(400, json=[{'errorCode': 'MALFORMED_ID'}])

        with self.assertRaises(httpx.HTTPStatusError) as context:
            webservice.Tools.get_http_response(URL, {})

        self.assertIn('MALFORMED_ID', str(context.exception))
        self.assertIs(context.exception.response, self.response)
        self.assertEqual(context.exception.response.status_code, 400)
        self.assertEqual(str(context.exception.request.url), URL)

    def test_non_json_error_still_raises_http_error(self):
        self.response = httpx.Response(503, text='<html>Service Unavailable</html>')

        with self.assertRaises(httpx.HTTPStatusError) as context:
            webservice.Tools.get_http_response(URL, {})

        self.assertIn('Service Unavailable', str(context.exception))
        self.assertEqual(context.exception.response.status_code, 503)

    def test_not_modified_is_not_an_error(self):
        self.response = httpx.Response(304)

        response = webservice.Tools.get_http_response(URL, {})

        self.assertEqual(response.status_code, 304)

    def test_access_token_is_not_sent_over_http(self):
        with self.assertRaises(ValueError):
            webservice.Tools.get_http_response('http://example.my.salesforce.com/services/data/',
                                               {'Authorization': 'Bearer token'})

        self.assertEqual(self.requests, [])

    def test_http_is_allowed_without_access_token(self):
        webservice.Tools.get_http_response('http://example.com/', {})

        self.assertEqual(len(self.requests), 1)

    def test_text_body_is_sent_as_is(self):
        webservice.Tools.post_http_response(URL, '{"Name": "Café"}', {'Content-Type': 'application/json'})

        self.assertEqual(self.requests[0].method, 'POST')
        self.assertEqual(self.requests[0].content, '{"Name": "Café"}'.encode('utf-8'))
        self.assertEqual(self.requests[0].headers['Content-Type'], 'application/json')

    def test_dict_body_is_sent_as_form_fields(self):
        webservice.Tools.post_http_response(URL, {'grant_type': 'password', 'username': 'user@example.com'}, '')

        self.assertEqual(self.requests[0].content, b'grant_type=password&username=user%40example.com')
        self.assertEqual(self.requests[0].headers['Content-Type'], 'application/x-www-form-urlencoded')

    def test_request_methods(self):
        cases = [(webservice.Tools.put_http_response, 'PUT'), (webservice.Tools.patch_http_response, 'PATCH'),
                 (webservice.Tools.delete_http_response, 'DELETE')]

        for method, expected in cases:
            with self.subTest(method=expected):
                method(URL, None, {})

                self.assertEqual(self.requests[-1].method, expected)
                self.assertEqual(self.requests[-1].content, b'')

    def test_multipart_files(self):
        files = {
            'entity_Document': (None, '{"Name": "report.pdf"}', 'application/json'),
            'Body': ('report.pdf', io.BytesIO(b'%PDF-1.4 data'), 'application/pdf')
        }

        webservice.Tools.post_http_response(URL, None, {'Authorization': 'Bearer token'}, files)

        request = self.requests[0]
        body = request.content
        self.assertTrue(request.headers['Content-Type'].startswith('multipart/form-data; boundary='))
        self.assertIn(b'Content-Disposition: form-data; name="entity_Document"\r\nContent-Type: application/json'
                      b'\r\n\r\n{"Name": "report.pdf"}', body)
        self.assertIn(b'Content-Disposition: form-data; name="Body"; filename="report.pdf"\r\n'
                      b'Content-Type: application/pdf\r\n\r\n%PDF-1.4 data', body)


class TestRedirects(unittest.TestCase):

    def test_redirects_are_followed(self):
        def handler(request):
            if request.url.path == '/old':
                return httpx.Response(302, headers={'Location': 'https://example.my.salesforce.com/new'})
            return httpx.Response(200, json={'path': request.url.path})

        client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)

        with mock.patch.object(webservice.Tools, 'client', client):
            response = webservice.Tools.get_http_response('https://example.my.salesforce.com/old', {})

        self.assertEqual(response.json(), {'path': '/new'})
        self.assertTrue(webservice.Tools.client.follow_redirects)


class TestConnectionReuse(unittest.TestCase):

    def test_requests_reuse_one_connection(self):
        connections = set()

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def do_GET(self):
                connections.add(self.client_address)
                self.send_response(200)
                self.send_header('Content-Length', '2')
                self.end_headers()
                self.wfile.write(b'{}')

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

        for _ in range(3):
            webservice.Tools.get_http_response('http://127.0.0.1:{}/'.format(server.server_port), {})

        self.assertEqual(len(connections), 1)


if __name__ == '__main__':
    unittest.main()
