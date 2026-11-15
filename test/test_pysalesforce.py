#!/usr/bin/python3
import contextlib
import datetime
import inspect
import io
import json
import unittest
from unittest import mock

import pysalesforceutils
from pysalesforceutils import Util, Authentication, Tooling, Standard, Bulk, Bulk2, Metadata, Salesforce

TOKEN = 'token'
INSTANCE = 'https://example.my.salesforce.com'
BASE = INSTANCE + '/services/data/v' + pysalesforceutils.API_VERSION


class MockedRequestTestCase(unittest.TestCase):

    def setUp(self):
        patcher = mock.patch('pysalesforceutils.webservice.Tools.http_request')
        self.http_request = patcher.start()
        self.http_request.return_value.text = '{}'
        self.addCleanup(patcher.stop)

    def requested_url(self):
        return self.http_request.call_args.kwargs['URL']

    def assert_request(self, method, url, body=None, headers=None):
        kwargs = self.http_request.call_args.kwargs

        self.assertEqual(kwargs['requestType'], method)
        self.assertEqual(kwargs['URL'], url)

        if body is None:
            self.assertIsNone(kwargs.get('data_body'))
        else:
            self.assertEqual(json.loads(kwargs['data_body']), body)

        expected_headers = {'Authorization': 'Bearer token', 'Content-Type': 'application/json'}
        expected_headers.update(headers or {})
        self.assertEqual(kwargs['header_details'], expected_headers)


class TestUrlEncoding(MockedRequestTestCase):
    """
    Values supplied by the caller must not be able to change which endpoint
    is called or add query parameters.
    """

    def test_valid_values_are_unchanged(self):
        Standard.get_sobject_row('Account', '001xx000003DGb2AAG', 'Id,Name,Owner.Name', TOKEN, INSTANCE)

        self.assertEqual(self.requested_url(),
                         BASE + '/sobjects/Account/001xx000003DGb2AAG?fields=Id,Name,Owner.Name')

    def test_record_id_cannot_traverse_to_another_endpoint(self):
        Standard.get_sobject_row('Account', '../../tooling/executeAnonymous/?anonymousBody=x', None, TOKEN, INSTANCE)

        self.assertEqual(self.requested_url(),
                         BASE + '/sobjects/Account/..%2F..%2Ftooling%2FexecuteAnonymous%2F%3FanonymousBody%3Dx')

    def test_dot_segments_are_rejected(self):
        with self.assertRaises(ValueError):
            Standard.get_sobject_row('Account', '..', None, TOKEN, INSTANCE)

        self.http_request.assert_not_called()

    def test_field_list_cannot_add_query_params(self):
        Standard.get_sobject_row('Account', '001xx000003DGb2AAG', 'Id&x=1', TOKEN, INSTANCE)

        self.assertEqual(self.requested_url(), BASE + '/sobjects/Account/001xx000003DGb2AAG?fields=Id%26x%3D1')

    def test_get_sobject_rows(self):
        Standard.get_sobject_rows('Account', '001A,001B&x=1', 'Id,Name', TOKEN, INSTANCE)

        self.assertEqual(self.requested_url(),
                         BASE + '/composite/sobjects/Account?ids=001A,001B%26x%3D1&fields=Id,Name')

    def test_delete_ids_cannot_override_all_or_none(self):
        Standard.delete_sobject_rows(['001A', '001B&allOrNone=true'], False, TOKEN, INSTANCE)

        self.assertEqual(self.requested_url(),
                         BASE + '/composite/sobjects?ids=001A,001B%26allOrNone%3Dtrue&allOrNone=false')

    def test_upsert_external_id_field(self):
        Standard.upsert_sobject_rows('Account', [], TOKEN, INSTANCE, external_id_field_name='Ext__c/../x')

        self.assertEqual(self.requested_url(), BASE + '/composite/sobjects/Account/Ext__c%2F..%2Fx')

    def test_bulk_batch_result(self):
        Bulk.get_batch_result('750A/x', '751B?y', TOKEN, INSTANCE)

        self.assertEqual(self.requested_url(),
                         INSTANCE + '/services/async/' + pysalesforceutils.API_VERSION +
                         '/job/750A%2Fx/batch/751B%3Fy/result')

    def test_bulk2_job_id(self):
        Bulk2.get_job_info('750A/../../x', TOKEN, INSTANCE)

        self.assertEqual(self.requested_url(), INSTANCE + Bulk2.base_bulk2_uri + '/750A%2F..%2F..%2Fx')


class TestTooling(MockedRequestTestCase):

    def test_query(self):
        self.http_request.return_value.text = '{"size": 0}'

        result = Tooling.query('SELECT Id FROM ApexClass', TOKEN, INSTANCE)

        self.assertEqual(result, {'size': 0})
        self.assertEqual(self.requested_url(), BASE + '/tooling/query/?q=SELECT%20Id%20FROM%20ApexClass')
        self.assertEqual(self.http_request.call_args.kwargs['requestType'], 'GET')
        self.assertEqual(self.http_request.call_args.kwargs['header_details'],
                         {'Authorization': 'Bearer token', 'Content-Type': 'application/json'})

    def test_execute_anonymous(self):
        Tooling.execute_anonymous('System.debug(1);', TOKEN, INSTANCE)

        self.assertEqual(self.requested_url(),
                         BASE + '/tooling/executeAnonymous/?anonymousBody=System.debug%281%29%3B')

    def test_completions(self):
        Tooling.completions('apex', TOKEN, INSTANCE)

        self.assertEqual(self.requested_url(), BASE + '/tooling/completions?type=apex')

    def test_run_tests_asynchronous_list(self):
        Tooling.run_tests_asynchronous_list(['01pA'], None, 2, 'RunSpecifiedTests', TOKEN, INSTANCE)

        self.assertEqual(self.requested_url(), BASE + '/tooling/runTestsAsynchronous/')
        self.assertEqual(self.http_request.call_args.kwargs['requestType'], 'POST')
        self.assertEqual(json.loads(self.http_request.call_args.kwargs['data_body']),
                         {'classids': ['01pA'], 'maxFailedTests': 2, 'testLevel': 'RunSpecifiedTests'})

    def test_run_tests_asynchronous_json(self):
        tests = [{'classId': '01pA', 'testMethods': ['testOne']}]

        Tooling.run_tests_asynchronous_json(tests, TOKEN, INSTANCE)

        self.assertEqual(self.requested_url(), BASE + '/tooling/runTestsAsynchronous/')
        self.assertEqual(json.loads(self.http_request.call_args.kwargs['data_body']), {'tests': tests})

    def test_api_version_can_be_overridden_at_runtime(self):
        with mock.patch.object(pysalesforceutils, 'API_VERSION', '60.0'):
            Tooling.query('SELECT Id FROM ApexClass', TOKEN, INSTANCE)

        self.assertEqual(self.requested_url(),
                         INSTANCE + '/services/data/v60.0/tooling/query/?q=SELECT%20Id%20FROM%20ApexClass')


class TestStandardRequests(MockedRequestTestCase):
    """
    Checks the HTTP method, URL, headers and body each Standard method sends.
    """
    RECORDS = [{'attributes': {'type': 'Account'}, 'Name': 'Acme'}]

    def test_get_sobject_row(self):
        self.http_request.return_value.text = '{"Id": "001A"}'

        result = Standard.get_sobject_row('Account', '001A', 'Id,Name', TOKEN, INSTANCE)

        self.assertEqual(result, {'Id': '001A'})
        self.assert_request('GET', BASE + '/sobjects/Account/001A?fields=Id,Name')

    def test_get_sobject_rows(self):
        Standard.get_sobject_rows('Account', '001A,001B', 'Id,Name', TOKEN, INSTANCE)

        self.assert_request('GET', BASE + '/composite/sobjects/Account?ids=001A,001B&fields=Id,Name')

    def test_get_sobject_blob_returns_the_response(self):
        result = Standard.get_sobject_blob('Attachment', '00PA', TOKEN, INSTANCE)

        self.assertIs(result, self.http_request.return_value)
        self.assert_request('GET', BASE + '/sobjects/Attachment/00PA/Body')

    def test_create_sobject_row(self):
        self.http_request.return_value.text = '{"id": "001A"}'

        result = Standard.create_sobject_row('Account', {'Name': 'Acme'}, True, TOKEN, INSTANCE)

        self.assertEqual(result, '{"id": "001A"}')
        self.assert_request('POST', BASE + '/sobjects/Account/', {'Name': 'Acme'}, {'Sforce-Auto-Assign': 'true'})

    def test_update_sobject_row(self):
        self.http_request.return_value.status_code = 204

        result = Standard.update_sobject_row('Account', '001A', {'Name': 'Acme'}, False, TOKEN, INSTANCE)

        self.assertEqual(result, 'Update Successful')
        self.assert_request('PATCH', BASE + '/sobjects/Account/001A', {'Name': 'Acme'},
                            {'Sforce-Auto-Assign': 'false'})

    def test_create_sobject_rows(self):
        self.http_request.return_value.text = '[{"success": true}]'

        result = Standard.create_sobject_rows(self.RECORDS, True, True, TOKEN, INSTANCE)

        self.assertEqual(result, [{'success': True}])
        self.assert_request('POST', BASE + '/composite/sobjects', {'allOrNone': True, 'records': self.RECORDS},
                            {'Sforce-Auto-Assign': 'true'})

    def test_update_sobject_rows(self):
        Standard.update_sobject_rows(self.RECORDS, False, False, TOKEN, INSTANCE)

        self.assert_request('PATCH', BASE + '/composite/sobjects', {'allOrNone': False, 'records': self.RECORDS},
                            {'Sforce-Auto-Assign': 'false'})

    def test_upsert_sobject_rows(self):
        Standard.upsert_sobject_rows('Account', self.RECORDS, TOKEN, INSTANCE, external_id_field_name='Ext__c')

        self.assert_request('PATCH', BASE + '/composite/sobjects/Account/Ext__c',
                            {'allOrNone': False, 'records': self.RECORDS}, {'Sforce-Auto-Assign': 'false'})

    def test_delete_sobject_rows(self):
        Standard.delete_sobject_rows(['001A', '001B'], True, TOKEN, INSTANCE)

        self.assert_request('DELETE', BASE + '/composite/sobjects?ids=001A,001B&allOrNone=true')

    def test_query_methods(self):
        cases = [(Standard.query, '/query/?q='), (Standard.query_all, '/queryAll/?q='),
                 (Standard.search, '/search/?q=')]

        for method, uri in cases:
            with self.subTest(uri=uri):
                method('SELECT Id FROM Account', TOKEN, INSTANCE)

                self.assert_request('GET', BASE + uri + 'SELECT%20Id%20FROM%20Account')

    def test_reset_users_password(self):
        Standard.reset_users_password('005A', TOKEN, INSTANCE)

        self.assert_request('DELETE', BASE + '/sobjects/User/005A/password')

    def test_get_current_user_info(self):
        Standard.get_current_user_info(TOKEN, INSTANCE)

        self.assert_request('GET', BASE + '/chatter/users/me')

    def test_post_chatter_mention(self):
        Standard.post_chatter_mention('hello', '005A', '001A', TOKEN, INSTANCE)

        self.assert_request('POST', BASE + '/chatter/feed-elements', {
            'body': {'messageSegments': [{'type': 'Mention', 'id': '005A'}, {'type': 'Text', 'text': 'hello'}]},
            'feedElementType': 'FeedItem',
            'subjectId': '001A'})

    def test_get_updated_and_deleted(self):
        start = datetime.datetime(2020, 3, 13, 12, 0, 0)
        end = datetime.datetime(2020, 3, 14, 12, 0, 0)
        params = '?start=2020-03-13T12%3A00%3A00Z&end=2020-03-14T12%3A00%3A00Z'

        Standard.get_updated('Account', start, end, TOKEN, INSTANCE)
        self.assert_request('GET', BASE + '/sobjects/Account/updated/' + params)

        Standard.get_deleted('Account', start, end, TOKEN, INSTANCE)
        self.assert_request('GET', BASE + '/sobjects/Account/deleted/' + params)

    def test_retrieve(self):
        Standard.retrieve('Account', ['001A'], ['Id', 'Name'], TOKEN, INSTANCE)

        self.assert_request('POST', BASE + '/composite/sobjects/Account', {'ids': ['001A'], 'fields': ['Id', 'Name']})

    def test_graph_composite_request(self):
        request_body = {'graphs': [{'graphId': 'graph1', 'compositeRequest': []}]}

        Standard.graph_composite_request(request_body, TOKEN, INSTANCE)

        self.assert_request('POST', BASE + '/composite/graph', request_body)

    def test_get_object_describe(self):
        Standard.get_object_describe('Account', None, TOKEN, INSTANCE)

        self.assert_request('GET', BASE + '/sobjects/Account/describe/')


class TestStandard(MockedRequestTestCase):

    def test_api_version_can_be_overridden_at_runtime(self):
        with mock.patch.object(pysalesforceutils, 'API_VERSION', '60.0'):
            Standard.query('SELECT Id FROM Account', TOKEN, INSTANCE)

        self.assertEqual(self.requested_url(),
                         INSTANCE + '/services/data/v60.0/query/?q=SELECT%20Id%20FROM%20Account')

    def test_get_sobject_rows_without_fields(self):
        Standard.get_sobject_rows('Account', '001A,001B', None, TOKEN, INSTANCE)

        self.assertEqual(self.requested_url(), BASE + '/composite/sobjects/Account?ids=001A,001B')

    def test_get_object_describe_modified_since_header(self):
        Standard.get_object_describe('Account', datetime.datetime(2020, 11, 6, 8, 49, 37), TOKEN, INSTANCE)

        headers = self.http_request.call_args.kwargs['header_details']
        self.assertEqual(headers['If-Modified-Since'], 'Fri, 06 Nov 2020 08:49:37 GMT')

    def test_get_object_describe_not_modified(self):
        self.http_request.return_value.status_code = 304
        self.http_request.return_value.text = ''

        result = Standard.get_object_describe('Account', datetime.datetime(2020, 11, 6), TOKEN, INSTANCE)

        self.assertIsNone(result)


class TestBulk2Requests(MockedRequestTestCase):
    """
    Checks the HTTP method, URL, headers and body each Bulk2 method sends.
    """
    INGEST = BASE + '/jobs/ingest'

    def test_get_job_list(self):
        Bulk2.get_job_list(True, 'V2Ingest', 5, TOKEN, INSTANCE)

        self.assert_request('GET', self.INGEST + '?isPkChunkingEnabled=true&jobType=V2Ingest&queryLocator=5')

    def test_create_job(self):
        self.http_request.return_value.text = '{"id": "750A"}'

        result = Bulk2.create_job('Account', 'upsert', 'Ext__c', 'COMMA', 'CSV', 'LF', TOKEN, INSTANCE)

        self.assertEqual(result, {'id': '750A'})
        self.assert_request(
            'POST', self.INGEST,
            {'object': 'Account', 'operation': 'upsert', 'externalIdFieldName': 'Ext__c', 'columnDelimiter': 'COMMA',
             'contentType': 'CSV', 'lineEnding': 'LF'},
            {'Content-Type': 'application/json; charset=UTF-8', 'Accept': 'application/json'})

    def test_upload_csv_batch_sends_the_csv_as_is(self):
        self.http_request.return_value.status_code = 201

        result = Bulk2.upload_csv_batch('Name\nAcme\n', '750A', TOKEN, INSTANCE)

        kwargs = self.http_request.call_args.kwargs
        self.assertEqual(result, 201)
        self.assertEqual(kwargs['requestType'], 'PUT')
        self.assertEqual(kwargs['URL'], self.INGEST + '/750A/batches')
        self.assertEqual(kwargs['data_body'], 'Name\nAcme\n')
        self.assertEqual(kwargs['header_details'], {'Authorization': 'Bearer token', 'Content-Type': 'text/csv',
                                                    'Accept': 'application/json'})

    def test_change_job_state(self):
        Bulk2.change_job_state('UploadComplete', '750A', TOKEN, INSTANCE)

        self.assert_request('PATCH', self.INGEST + '/750A', {'state': 'UploadComplete'})

    def test_delete_job(self):
        self.http_request.return_value.status_code = 204

        result = Bulk2.delete_job('750A', TOKEN, INSTANCE)

        self.assertEqual(result, 204)
        self.assert_request('DELETE', self.INGEST + '/750A')

    def test_get_job_info(self):
        Bulk2.get_job_info('750A', TOKEN, INSTANCE)

        self.assert_request('GET', self.INGEST + '/750A')

    def test_result_downloads_return_text(self):
        cases = [(Bulk2.get_success_results, '/successfulResults/'), (Bulk2.get_failed_results, '/failedResults/'),
                 (Bulk2.get_unprocessed_results, '/unprocessedrecords/')]
        self.http_request.return_value.text = 'sf__Id,Name\n001A,Acme\n'

        for method, uri in cases:
            with self.subTest(uri=uri):
                result = method('750A', TOKEN, INSTANCE)

                self.assertEqual(result, 'sf__Id,Name\n001A,Acme\n')
                self.assert_request('GET', self.INGEST + '/750A' + uri)

    def test_api_version_can_be_overridden_at_runtime(self):
        with mock.patch.object(pysalesforceutils, 'API_VERSION', '60.0'):
            Bulk2.get_job_info('750A', TOKEN, INSTANCE)

        self.assertEqual(self.requested_url(), INSTANCE + '/services/data/v60.0/jobs/ingest/750A')


class TestBulkRequests(MockedRequestTestCase):
    """
    Checks the sequence of HTTP requests the Bulk methods send.
    """
    ASYNC = INSTANCE + '/services/async/' + pysalesforceutils.API_VERSION
    BULK_HEADER = {'Authorization': 'Bearer token', 'Content-Type': 'application/json', 'X-SFDC-Session': 'token'}

    def respond_with(self, *bodies):
        responses = []
        for body in bodies:
            response = mock.Mock()
            response.text = json.dumps(body)
            responses.append(response)
        self.http_request.side_effect = responses

    def requests_sent(self):
        requests_sent = []
        for call in self.http_request.call_args_list:
            self.assertEqual(call.kwargs['header_details'], self.BULK_HEADER)
            body = call.kwargs.get('data_body')
            try:
                body = json.loads(body)
            except (TypeError, ValueError):
                pass
            requests_sent.append((call.kwargs['requestType'], call.kwargs['URL'], body))

        return requests_sent

    def test_get_batch_result(self):
        self.respond_with([{'success': True}])

        result = Bulk.get_batch_result('750A', '751A', TOKEN, INSTANCE)

        self.assertEqual(result, [{'success': True}])
        self.assertEqual(self.requests_sent(), [('GET', self.ASYNC + '/job/750A/batch/751A/result', None)])

    def test_get_query_result(self):
        self.respond_with([{'Id': '001A'}])

        result = Bulk.get_query_result('750A', '751A', '752A', TOKEN, INSTANCE)

        self.assertEqual(result, [{'Id': '001A'}])
        self.assertEqual(self.requests_sent(), [('GET', self.ASYNC + '/job/750A/batch/751A/result/752A', None)])

    def test_upsert_sobject_rows(self):
        records = [{'Name': 'A'}, {'Name': 'B'}, {'Name': 'C'}]
        self.respond_with(
            {'id': '750A'}, {'id': '751A'}, {'id': '751B'}, {'state': 'Closed'},
            {'numberBatchesCompleted': 2, 'numberBatchesFailed': 0, 'numberBatchesTotal': 2},
            [{'id': '001A'}, {'id': '001B'}], [{'id': '001C'}])

        with contextlib.redirect_stdout(io.StringIO()):
            result = Bulk.upsert_sobject_rows('Account', records, 2, 0, TOKEN, INSTANCE, 'Ext__c')

        self.assertEqual(result, [{'id': '001A'}, {'id': '001B'}, {'id': '001C'}])
        self.assertEqual(self.requests_sent(), [
            ('POST', self.ASYNC + '/job/', {'operation': 'upsert', 'object': 'Account', 'contentType': 'JSON',
                                            'externalIdFieldName': 'Ext__c'}),
            ('POST', self.ASYNC + '/job/750A/batch', [{'Name': 'A'}, {'Name': 'B'}]),
            ('POST', self.ASYNC + '/job/750A/batch', [{'Name': 'C'}]),
            ('POST', self.ASYNC + '/job/750A', {'state': 'Closed'}),
            ('GET', self.ASYNC + '/job/750A', None),
            ('GET', self.ASYNC + '/job/750A/batch/751A/result', None),
            ('GET', self.ASYNC + '/job/750A/batch/751B/result', None),
        ])

    def test_query_sobject_rows(self):
        self.respond_with(
            {'id': '750A'}, {'id': '751A'}, {'state': 'Closed'},
            {'numberBatchesCompleted': 1, 'numberBatchesFailed': 0, 'numberBatchesTotal': 1},
            ['752A'], [{'Id': '001A'}])

        result = Bulk.query_sobject_rows('Account', 'SELECT Id FROM Account', True, TOKEN, INSTANCE, verbose=False)

        self.assertEqual(result, [{'Id': '001A'}])
        self.assertEqual(self.requests_sent(), [
            ('POST', self.ASYNC + '/job/', {'operation': 'queryAll', 'object': 'Account', 'contentType': 'JSON'}),
            ('POST', self.ASYNC + '/job/750A/batch', 'SELECT Id FROM Account'),
            ('POST', self.ASYNC + '/job/750A', {'state': 'Closed'}),
            ('GET', self.ASYNC + '/job/750A', None),
            ('GET', self.ASYNC + '/job/750A/batch/751A/result', None),
            ('GET', self.ASYNC + '/job/750A/batch/751A/result/752A', None),
        ])

    def test_api_version_can_be_overridden_at_runtime(self):
        self.respond_with([])

        with mock.patch.object(pysalesforceutils, 'API_VERSION', '60.0'):
            Bulk.get_batch_result('750A', '751A', TOKEN, INSTANCE)

        self.assertEqual(self.requested_url(), INSTANCE + '/services/async/60.0/job/750A/batch/751A/result')


class TestBulkPolling(MockedRequestTestCase):

    def setUp(self):
        super().setUp()
        patcher = mock.patch('time.sleep')
        self.sleep = patcher.start()
        self.addCleanup(patcher.stop)

    def test_bulk_job_status_stops_when_job_is_aborted(self):
        self.http_request.return_value.text = json.dumps({
            'state': 'Aborted', 'numberBatchesCompleted': 0, 'numberBatchesFailed': 0, 'numberBatchesTotal': 2})

        result = Bulk.get_job_status('750A', 5, False, TOKEN, INSTANCE)

        self.assertEqual(result['state'], 'Aborted')
        self.sleep.assert_not_called()

    def test_bulk_job_status_keeps_polling_until_batches_finish(self):
        responses = []
        for completed in (0, 1, 2):
            response = mock.Mock()
            response.text = json.dumps({
                'state': 'Closed', 'numberBatchesCompleted': completed, 'numberBatchesFailed': 0,
                'numberBatchesTotal': 2})
            responses.append(response)
        self.http_request.side_effect = responses

        result = Bulk.get_job_status('750A', 5, False, TOKEN, INSTANCE)

        self.assertEqual(result['numberBatchesCompleted'], 2)
        self.assertEqual(self.sleep.call_count, 2)
        self.assertEqual(self.requested_url(),
                         INSTANCE + '/services/async/' + pysalesforceutils.API_VERSION + '/job/750A')

    def test_bulk2_job_status_returns_as_soon_as_job_completes(self):
        self.http_request.return_value.text = json.dumps({
            'state': 'JobComplete', 'numberRecordsFailed': 0, 'numberRecordsProcessed': 5})

        result = Bulk2.get_job_status('750A', 5, False, TOKEN, INSTANCE)

        self.assertEqual(result['state'], 'JobComplete')
        self.sleep.assert_not_called()

    def test_bulk2_job_list_returns_response(self):
        self.http_request.return_value.text = json.dumps({'done': True, 'records': []})

        result = Bulk2.get_job_list(None, 'V2Ingest', None, TOKEN, INSTANCE)

        self.assertEqual(result, {'done': True, 'records': []})
        self.assertEqual(self.requested_url(), INSTANCE + Bulk2.base_bulk2_uri + '?jobType=V2Ingest')


class TestSalesforceClient(MockedRequestTestCase):

    def setUp(self):
        super().setUp()
        self.sf = Salesforce(TOKEN, INSTANCE)

    def test_standard_method_fills_in_token_and_instance(self):
        self.http_request.return_value.text = '{"totalSize": 0}'

        result = self.sf.standard.query('SELECT Id FROM Account')

        self.assertEqual(result, {'totalSize': 0})
        self.assert_request('GET', BASE + '/query/?q=SELECT%20Id%20FROM%20Account')

    def test_arguments_after_the_token_can_be_positional_or_keyword(self):
        records = [{'attributes': {'type': 'Account'}, 'Name': 'Acme'}]

        self.sf.standard.upsert_sobject_rows('Account', records, True, external_id_field_name='Ext__c')

        self.assert_request('PATCH', BASE + '/composite/sobjects/Account/Ext__c',
                            {'allOrNone': True, 'records': records}, {'Sforce-Auto-Assign': 'false'})

    def test_tooling_bulk_and_bulk2(self):
        self.sf.tooling.query('SELECT Id FROM ApexClass')
        self.assert_request('GET', BASE + '/tooling/query/?q=SELECT%20Id%20FROM%20ApexClass')

        self.sf.bulk2.get_job_info('750A')
        self.assert_request('GET', BASE + '/jobs/ingest/750A')

        self.http_request.return_value.text = '[]'
        self.sf.bulk.get_batch_result('750A', '751A')
        self.assert_request('GET', INSTANCE + '/services/async/' + pysalesforceutils.API_VERSION +
                            '/job/750A/batch/751A/result', headers={'X-SFDC-Session': 'token'})

    def test_changed_access_token_is_used(self):
        self.sf.access_token = 'refreshed'

        self.sf.standard.get_current_user_info()

        self.assertEqual(self.http_request.call_args.kwargs['header_details']['Authorization'], 'Bearer refreshed')

    def test_every_api_method_is_available(self):
        for name, api_class in (('standard', Standard), ('tooling', Tooling), ('bulk', Bulk), ('bulk2', Bulk2)):
            expected = {method for method, value in vars(api_class).items() if isinstance(value, staticmethod)}

            self.assertEqual(set(vars(getattr(self.sf, name))), expected)

    def test_signature_and_docstring(self):
        method = self.sf.standard.get_sobject_row

        self.assertEqual(list(inspect.signature(method).parameters), ['object_name', 'record_id', 'field_list_string'])
        self.assertEqual(method.__doc__, Standard.get_sobject_row.__doc__)

    def test_missing_argument_raises_type_error(self):
        with self.assertRaises(TypeError):
            self.sf.standard.get_sobject_row('Account')

        self.http_request.assert_not_called()

    def test_login_and_logout(self):
        login_response = {'access_token': 'abc', 'instance_url': 'https://sandbox.my.salesforce.com'}

        with mock.patch.object(Authentication, 'get_oauth_login', return_value=login_response) as login:
            sf = Salesforce.login('user', 'password', 'client id', 'client secret', False)

        login.assert_called_once_with('user', 'password', 'client id', 'client secret', False)
        self.assertEqual((sf.access_token, sf.instance_url), ('abc', 'https://sandbox.my.salesforce.com'))

        self.http_request.return_value.status_code = 200
        result = sf.logout()

        kwargs = self.http_request.call_args.kwargs
        self.assertEqual(result, {'success': True, 'status_code': 200})
        self.assertEqual(kwargs['requestType'], 'POST')
        self.assertEqual(kwargs['URL'], 'https://sandbox.my.salesforce.com/services/oauth2/revoke')
        self.assertEqual(kwargs['data_body'], {'token': 'abc'})

    def test_revoke_token_is_not_sent_over_http(self):
        with self.assertRaises(ValueError):
            Authentication.revoke_token('abc', 'http://sandbox.my.salesforce.com')

        self.http_request.assert_not_called()


class TestClientCredentialsLogin(MockedRequestTestCase):
    LOGIN_RESPONSE = {'access_token': 'abc', 'instance_url': 'https://acme.my.salesforce.com'}

    def setUp(self):
        super().setUp()
        self.http_request.return_value.text = json.dumps(self.LOGIN_RESPONSE)

    def test_get_client_credentials_login(self):
        result = Authentication.get_client_credentials_login('client id', 'client secret',
                                                             'https://acme.my.salesforce.com/')

        kwargs = self.http_request.call_args.kwargs
        self.assertEqual(result, self.LOGIN_RESPONSE)
        self.assertEqual(kwargs['requestType'], 'POST')
        self.assertEqual(kwargs['URL'], 'https://acme.my.salesforce.com/services/oauth2/token')
        self.assertEqual(kwargs['data_body'], {'grant_type': 'client_credentials', 'client_id': 'client id',
                                               'client_secret': 'client secret'})

    def test_client_secret_is_not_sent_over_http(self):
        with self.assertRaises(ValueError):
            Authentication.get_client_credentials_login('client id', 'client secret', 'http://acme.my.salesforce.com')

        self.http_request.assert_not_called()

    def test_salesforce_login_client_credentials(self):
        sf = Salesforce.login_client_credentials('client id', 'client secret', 'https://acme.my.salesforce.com')

        self.assertEqual((sf.access_token, sf.instance_url), ('abc', 'https://acme.my.salesforce.com'))


class TestSoqlQuote(unittest.TestCase):

    def test_plain_value(self):
        self.assertEqual(Util.soql_quote('Acme'), "'Acme'")

    def test_quote_cannot_end_the_string(self):
        self.assertEqual(Util.soql_quote("x' OR Name != '"), "'x\\' OR Name != \\''")

    def test_backslash_is_escaped_before_quote(self):
        self.assertEqual(Util.soql_quote("a\\' OR 1"), "'a\\\\\\' OR 1'")

    def test_control_characters(self):
        self.assertEqual(Util.soql_quote('a\nb\rc\td'), "'a\\nb\\rc\\td'")

    def test_only_strings_are_accepted(self):
        for value in (None, 5, b'Acme'):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    Util.soql_quote(value)


class TestSoapClientCache(unittest.TestCase):

    def setUp(self):
        for patcher in (mock.patch('pysalesforceutils.util.Client'),
                        mock.patch.dict('pysalesforceutils.util._soap_clients', clear=True)):
            patcher.start()
            self.addCleanup(patcher.stop)

        self.client_class = pysalesforceutils.util.Client
        self.client_class.side_effect = lambda wsdl_file: mock.Mock(name=wsdl_file)

    def test_same_wsdl_is_only_loaded_once(self):
        first = Util.get_soap_client('metadata.wsdl')
        second = Util.get_soap_client('metadata.wsdl')

        self.assertIs(first, second)
        self.client_class.assert_called_once_with('metadata.wsdl')

    def test_each_wsdl_gets_its_own_client(self):
        metadata = Util.get_soap_client('metadata.wsdl')
        partner = Util.get_soap_client('partner.wsdl')

        self.assertIsNot(metadata, partner)
        self.assertEqual(self.client_class.call_count, 2)

    def test_metadata_headers_load_the_wsdl_once(self):
        Metadata.get_soap_headers('session', 'client', True, [])

        self.client_class.assert_called_once_with(pysalesforceutils.METADATA_WSDL_FILE)


class TestMetadataValidation(unittest.TestCase):

    def test_get_package_requires_version(self):
        with self.assertRaises(ValueError):
            Metadata.get_package(full_name='MyPackage')

    def test_get_retrieve_request_requires_api_version(self):
        with self.assertRaises(ValueError):
            Metadata.get_retrieve_request(single_package=True)

    def test_client_service_requires_https(self):
        with self.assertRaises(ValueError):
            Metadata.get_client_service('http://example.my.salesforce.com/services/Soap/m/50.0')


if __name__ == '__main__':
    unittest.main()
