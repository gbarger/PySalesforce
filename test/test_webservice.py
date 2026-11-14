#!/usr/bin/python3
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


if __name__ == '__main__':
    unittest.main()
