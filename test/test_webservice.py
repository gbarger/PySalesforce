#!/usr/bin/python3
import http.server
import threading
import unittest
from unittest import mock

import requests

from pysalesforceutils import webservice

URL = 'https://example.my.salesforce.com/services/data/'


def build_response(status_code, body):
    response = requests.Response()
    response.status_code = status_code
    response._content = body
    response.url = URL

    return response


class TestWebservice(unittest.TestCase):

    def setUp(self):
        patcher = mock.patch('requests.Session.send')
        self.send = patcher.start()
        self.addCleanup(patcher.stop)

    def test_http_request_returns_response(self):
        self.send.return_value = build_response(200, b'{"ok": true}')

        response = webservice.Tools.get_http_response(URL, {})

        self.assertEqual(response.json(), {'ok': True})

    def test_http_request_uses_default_timeout(self):
        self.send.return_value = build_response(200, b'{}')

        webservice.Tools.get_http_response(URL, {})

        self.assertEqual(webservice.Tools.default_timeout, 120)
        self.assertEqual(self.send.call_args.kwargs['timeout'], 120)

    def test_json_error_keeps_body_and_response(self):
        error_response = build_response(400, b'[{"errorCode": "MALFORMED_ID"}]')
        self.send.return_value = error_response

        with self.assertRaises(requests.exceptions.HTTPError) as context:
            webservice.Tools.get_http_response(URL, {})

        self.assertIn('MALFORMED_ID', str(context.exception))
        self.assertIs(context.exception.response, error_response)
        self.assertEqual(context.exception.response.status_code, 400)

    def test_non_json_error_still_raises_http_error(self):
        self.send.return_value = build_response(503, b'<html>Service Unavailable</html>')

        with self.assertRaises(requests.exceptions.HTTPError) as context:
            webservice.Tools.get_http_response(URL, {})

        self.assertIn('Service Unavailable', str(context.exception))
        self.assertEqual(context.exception.response.status_code, 503)

    def test_access_token_is_not_sent_over_http(self):
        with self.assertRaises(ValueError):
            webservice.Tools.get_http_response('http://example.my.salesforce.com/services/data/',
                                               {'Authorization': 'Bearer token'})

        self.send.assert_not_called()

    def test_http_is_allowed_without_access_token(self):
        self.send.return_value = build_response(200, b'{}')

        webservice.Tools.get_http_response('http://example.com/', {})

        self.send.assert_called_once()


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
