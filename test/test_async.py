#!/usr/bin/python3
import asyncio
import inspect
import json
import unittest
from unittest import mock

import httpx

import pysalesforceutils
from pysalesforceutils import AsyncSalesforce, Bulk, Bulk2, Salesforce, Standard, Tooling

TOKEN = 'token'
INSTANCE = 'https://example.my.salesforce.com'
BASE = INSTANCE + '/services/data/v' + pysalesforceutils.API_VERSION
LOGIN_RESPONSE = {'access_token': 'abc', 'instance_url': INSTANCE}


class AsyncTestCase(unittest.IsolatedAsyncioTestCase):
    """
    These tests send the requests through httpx to a handler function instead
    of the network, so they check the request that would really be sent.
    Every httpx.AsyncClient the package creates uses the handler.
    """

    async def asyncSetUp(self):
        self.requests = []
        self.responses = []

        async def handler(request):
            await request.aread()
            self.requests.append(request)

            if self.responses:
                return self.responses.pop(0)

            return httpx.Response(200, json={})

        self.real_async_client = httpx.AsyncClient
        patcher = mock.patch('pysalesforceutils.client.httpx.AsyncClient',
                             lambda **kwargs: self.real_async_client(transport=httpx.MockTransport(handler), **kwargs))
        patcher.start()
        self.addCleanup(patcher.stop)

        self.sf = AsyncSalesforce(TOKEN, INSTANCE)
        self.addAsyncCleanup(self.sf.aclose)


class TestAsyncSalesforce(AsyncTestCase):

    async def test_query_sends_request_and_returns_json(self):
        self.responses.append(httpx.Response(200, json={'totalSize': 0}))

        result = await self.sf.standard.query('SELECT Id FROM Account')

        self.assertEqual(result, {'totalSize': 0})
        request = self.requests[0]
        self.assertEqual(request.method, 'GET')
        self.assertEqual(str(request.url), BASE + '/query/?q=SELECT%20Id%20FROM%20Account')
        self.assertEqual(request.headers['Authorization'], 'Bearer token')

    async def test_json_body_is_sent(self):
        await self.sf.tooling.create_sobject_row('TraceFlag', {'LogType': 'DEVELOPER_LOG'})

        self.assertEqual(self.requests[0].method, 'POST')
        self.assertEqual(json.loads(self.requests[0].content), {'LogType': 'DEVELOPER_LOG'})

    async def test_error_response_raises_with_body(self):
        self.responses.append(httpx.Response(404, json=[{'errorCode': 'NOT_FOUND'}]))

        with self.assertRaises(httpx.HTTPStatusError) as context:
            await self.sf.standard.get_sobject_row('Account', '001A', None)

        self.assertIn('NOT_FOUND', str(context.exception))
        self.assertEqual(context.exception.response.status_code, 404)

    async def test_token_is_not_sent_over_http(self):
        self.sf.instance_url = 'http://example.my.salesforce.com'

        with self.assertRaises(ValueError):
            await self.sf.standard.get_current_user_info()

        self.assertEqual(self.requests, [])

    async def test_polling_uses_asyncio_sleep(self):
        self.responses.append(httpx.Response(200, json={'state': 'InProgress', 'numberRecordsProcessed': 0, 'numberRecordsFailed': 0}))
        self.responses.append(httpx.Response(200, json={'state': 'JobComplete', 'numberRecordsProcessed': 5,
                                                         'numberRecordsFailed': 0}))

        with mock.patch('asyncio.sleep', new_callable=mock.AsyncMock) as async_sleep, \
                mock.patch('time.sleep') as time_sleep:
            result = await self.sf.bulk2.get_job_status('750A', 5, False)

        self.assertEqual(result['state'], 'JobComplete')
        async_sleep.assert_awaited_once_with(5)
        time_sleep.assert_not_called()

    async def test_requests_run_concurrently(self):
        # the first request only finishes once the second one has started,
        # which can only happen if the first doesn't block the event loop
        second_started = asyncio.Event()

        async def handler(request):
            if 'Second' in str(request.url):
                second_started.set()
            else:
                await asyncio.wait_for(second_started.wait(), 5)

            return httpx.Response(200, json={'url': str(request.url)})

        await self.sf.http_client.aclose()
        self.sf.http_client = self.real_async_client(transport=httpx.MockTransport(handler))
        self.addAsyncCleanup(self.sf.http_client.aclose)

        first, second = await asyncio.gather(self.sf.standard.query('First'), self.sf.standard.query('Second'))

        self.assertTrue(first['url'].endswith('First'))
        self.assertTrue(second['url'].endswith('Second'))

    async def test_every_api_method_is_available_as_a_coroutine(self):
        sync_client = Salesforce(TOKEN, INSTANCE)

        for name, api_class in (('standard', Standard), ('tooling', Tooling), ('bulk', Bulk), ('bulk2', Bulk2)):
            expected = {method for method, value in vars(api_class).items() if isinstance(value, staticmethod)}
            async_api = getattr(self.sf, name)

            self.assertEqual(set(vars(async_api)), expected)

            for method_name in expected:
                async_method = getattr(async_api, method_name)
                sync_method = getattr(getattr(sync_client, name), method_name)

                self.assertTrue(inspect.iscoroutinefunction(async_method), method_name)
                self.assertEqual(inspect.signature(async_method), inspect.signature(sync_method))
                self.assertEqual(async_method.__doc__, sync_method.__doc__)

    async def test_missing_argument_raises_type_error(self):
        with self.assertRaises(TypeError):
            await self.sf.standard.get_sobject_row('Account')

        self.assertEqual(self.requests, [])


class TestAsyncLogin(AsyncTestCase):

    async def test_login_and_logout(self):
        self.responses.append(httpx.Response(200, json=LOGIN_RESPONSE))

        sf = await AsyncSalesforce.login('user', 'password', 'client id', 'client secret', False)
        self.addAsyncCleanup(sf.aclose)

        self.assertEqual((sf.access_token, sf.instance_url), ('abc', INSTANCE))
        self.assertEqual(str(self.requests[0].url), 'https://test.salesforce.com/services/oauth2/token')
        self.assertIn(b'grant_type=password', self.requests[0].content)

        result = await sf.logout()

        self.assertEqual(result, {'success': True, 'status_code': 200})
        self.assertEqual(str(self.requests[1].url), INSTANCE + '/services/oauth2/revoke')
        self.assertEqual(self.requests[1].content, b'token=abc')

    async def test_client_credentials_login(self):
        self.responses.append(httpx.Response(200, json=LOGIN_RESPONSE))

        sf = await AsyncSalesforce.login_client_credentials('client id', 'client secret', INSTANCE)
        self.addAsyncCleanup(sf.aclose)

        self.assertEqual(sf.access_token, 'abc')
        self.assertEqual(str(self.requests[0].url), INSTANCE + '/services/oauth2/token')
        self.assertIn(b'grant_type=client_credentials', self.requests[0].content)

    async def test_async_with_closes_connections(self):
        self.responses.append(httpx.Response(200, json=LOGIN_RESPONSE))

        async with await AsyncSalesforce.login('user', 'password', 'client id', 'client secret') as sf:
            await sf.standard.get_current_user_info()

        self.assertTrue(sf.http_client.is_closed)

    async def test_failed_login_closes_connections(self):
        self.responses.append(httpx.Response(400, json={'error': 'invalid_grant'}))
        created = []
        original_init = AsyncSalesforce.__init__

        def recording_init(client, *args):
            original_init(client, *args)
            created.append(client)

        with mock.patch.object(AsyncSalesforce, '__init__', recording_init):
            with self.assertRaises(httpx.HTTPStatusError):
                await AsyncSalesforce.login('user', 'password', 'client id', 'client secret')

        self.assertTrue(created[0].http_client.is_closed)


class TestAsyncHttpRequest(unittest.IsolatedAsyncioTestCase):

    async def test_uses_default_timeout_and_form_body(self):
        requests = []

        def handler(request):
            request.read()
            requests.append(request)
            return httpx.Response(200)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await pysalesforceutils.webservice.Tools.async_http_request(
                client, requestType='POST', URL=INSTANCE, data_body={'a': '1'}, header_details='')

        self.assertEqual(requests[0].content, b'a=1')
        self.assertEqual(requests[0].extensions['timeout'], {'connect': 120, 'read': 120, 'write': 120, 'pool': 120})

    async def test_not_modified_is_not_an_error(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(304))) as client:
            response = await pysalesforceutils.webservice.Tools.async_http_request(
                client, requestType='GET', URL=INSTANCE)

        self.assertEqual(response.status_code, 304)


if __name__ == '__main__':
    unittest.main()
