#!/usr/bin/python3
import contextlib
import datetime
import inspect
import io
import json
import time
import unittest
from unittest import mock

try:
    import jwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
except ImportError:
    jwt = None

import pysalesforceutils
from pysalesforceutils import (Util, Authentication, Tooling, Standard, Bulk, Bulk2, Metadata, Salesforce,
                               Composite)
from pysalesforceutils import util

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

    def test_delete_sobject_row(self):
        self.http_request.return_value.status_code = 204

        result = Standard.delete_sobject_row('Account', '001A', TOKEN, INSTANCE)

        self.assertEqual(result, 'Delete Successful')
        self.assert_request('DELETE', BASE + '/sobjects/Account/001A')

    def test_get_sobject_row_by_external_id(self):
        self.http_request.return_value.text = '{"Id": "001A"}'

        result = Standard.get_sobject_row_by_external_id('Account', 'Ext__c', 'A/1', 'Id,Name', TOKEN, INSTANCE)

        self.assertEqual(result, {'Id': '001A'})
        self.assert_request('GET', BASE + '/sobjects/Account/Ext__c/A%2F1?fields=Id,Name')

    def test_get_sobject_row_by_external_id_without_fields(self):
        Standard.get_sobject_row_by_external_id('Account', 'Number__c', 42, None, TOKEN, INSTANCE)

        self.assert_request('GET', BASE + '/sobjects/Account/Number__c/42')

    def test_upsert_sobject_row_by_external_id(self):
        self.http_request.return_value.text = '{"id": "001A", "success": true, "errors": [], "created": true}'

        result = Standard.upsert_sobject_row_by_external_id('Account', 'Ext__c', 'A1', {'Name': 'Acme'}, TOKEN,
                                                            INSTANCE)

        self.assertEqual(result, {'id': '001A', 'success': True, 'errors': [], 'created': True})
        self.assert_request('PATCH', BASE + '/sobjects/Account/Ext__c/A1', {'Name': 'Acme'})

    def test_upsert_sobject_row_by_external_id_with_no_response_body(self):
        self.http_request.return_value.status_code = 204
        self.http_request.return_value.text = ''

        result = Standard.upsert_sobject_row_by_external_id('Account', 'Ext__c', 'A1', {'Name': 'Acme'}, TOKEN,
                                                            INSTANCE)

        self.assertEqual(result, 'Update Successful')

    def test_delete_sobject_row_by_external_id(self):
        self.http_request.return_value.status_code = 204

        result = Standard.delete_sobject_row_by_external_id('Account', 'Ext__c', 'A1', TOKEN, INSTANCE)

        self.assertEqual(result, 'Delete Successful')
        self.assert_request('DELETE', BASE + '/sobjects/Account/Ext__c/A1')

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

    def test_composite_request(self):
        subrequests = [
            {'method': 'POST', 'url': '/services/data/v67.0/sobjects/Account/', 'referenceId': 'account',
             'body': {'Name': 'Acme'}},
            {'method': 'GET', 'url': '/services/data/v67.0/sobjects/Account/@{account.id}', 'referenceId': 'lookup'}]
        self.http_request.return_value.text = '{"compositeResponse": []}'

        result = Standard.composite_request(subrequests, True, TOKEN, INSTANCE)

        self.assertEqual(result, {'compositeResponse': []})
        self.assert_request('POST', BASE + '/composite',
                            {'allOrNone': True, 'collateSubrequests': True, 'compositeRequest': subrequests})

    def test_composite_request_without_collating(self):
        Standard.composite_request([], False, TOKEN, INSTANCE, collate_subrequests=False)

        self.assert_request('POST', BASE + '/composite',
                            {'allOrNone': False, 'collateSubrequests': False, 'compositeRequest': []})

    def test_composite_batch_request(self):
        subrequests = [
            {'method': 'PATCH', 'url': 'v67.0/sobjects/Account/001A', 'richInput': {'Name': 'Acme'}},
            {'method': 'GET', 'url': 'v67.0/sobjects/Account/001A?fields=Name'}]

        Standard.composite_batch_request(subrequests, True, TOKEN, INSTANCE)

        self.assert_request('POST', BASE + '/composite/batch', {'haltOnError': True, 'batchRequests': subrequests})

    def test_composite_batch_request_converts_composite_subrequests(self):
        subrequests = [
            {'method': 'PATCH', 'url': '/services/data/v67.0/sobjects/Account/001A', 'referenceId': 'update',
             'body': {'Name': 'Acme'}},
            {'method': 'GET', 'url': '/services/data/v67.0/sobjects/Account/001A?fields=Name', 'referenceId': 'get'}]

        Standard.composite_batch_request(subrequests, False, TOKEN, INSTANCE)

        self.assert_request('POST', BASE + '/composite/batch', {'haltOnError': False, 'batchRequests': [
            {'method': 'PATCH', 'url': 'v67.0/sobjects/Account/001A', 'richInput': {'Name': 'Acme'}},
            {'method': 'GET', 'url': 'v67.0/sobjects/Account/001A?fields=Name'}]})
        # the caller's subrequests aren't changed
        self.assertEqual(subrequests[0]['url'], '/services/data/v67.0/sobjects/Account/001A')
        self.assertIn('referenceId', subrequests[0])

    def test_create_sobject_tree(self):
        records = [{'attributes': {'type': 'Account', 'referenceId': 'ref1'}, 'Name': 'Acme', 'Contacts': {
            'records': [{'attributes': {'type': 'Contact', 'referenceId': 'ref2'}, 'LastName': 'Smith'}]}}]
        self.http_request.return_value.text = '{"hasErrors": false, "results": []}'

        result = Standard.create_sobject_tree('Account', records, TOKEN, INSTANCE)

        self.assertEqual(result, {'hasErrors': False, 'results': []})
        self.assert_request('POST', BASE + '/composite/tree/Account', {'records': records})

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


class TestComposite(MockedRequestTestCase):
    VERSIONED = '/services/data/v' + pysalesforceutils.API_VERSION

    def test_builders(self):
        cases = [
            (Composite.create('a', 'Account', {'Name': 'Acme'}),
             {'method': 'POST', 'url': self.VERSIONED + '/sobjects/Account/', 'referenceId': 'a',
              'body': {'Name': 'Acme'}}),
            (Composite.update('b', 'Account', '001A', {'Name': 'Acme'}),
             {'method': 'PATCH', 'url': self.VERSIONED + '/sobjects/Account/001A', 'referenceId': 'b',
              'body': {'Name': 'Acme'}}),
            (Composite.upsert('c', 'Account', 'Ext__c', 'A/1', {'Name': 'Acme'}),
             {'method': 'PATCH', 'url': self.VERSIONED + '/sobjects/Account/Ext__c/A%2F1', 'referenceId': 'c',
              'body': {'Name': 'Acme'}}),
            (Composite.delete('d', 'Account', '001A'),
             {'method': 'DELETE', 'url': self.VERSIONED + '/sobjects/Account/001A', 'referenceId': 'd'}),
            (Composite.get('e', 'Account', '001A'),
             {'method': 'GET', 'url': self.VERSIONED + '/sobjects/Account/001A', 'referenceId': 'e'}),
            (Composite.get('f', 'Account', '001A', 'Id,Name'),
             {'method': 'GET', 'url': self.VERSIONED + '/sobjects/Account/001A?fields=Id,Name', 'referenceId': 'f'}),
            (Composite.query('g', 'SELECT Id FROM Account'),
             {'method': 'GET', 'url': self.VERSIONED + '/query/?q=SELECT%20Id%20FROM%20Account', 'referenceId': 'g'}),
            (Composite.request('h', 'GET', '/limits'),
             {'method': 'GET', 'url': self.VERSIONED + '/limits', 'referenceId': 'h'}),
        ]

        for subrequest, expected in cases:
            with self.subTest(reference_id=expected['referenceId']):
                self.assertEqual(subrequest, expected)

    def test_references_to_other_subrequests_are_kept(self):
        self.assertEqual(Composite.get('lookup', 'Account', '@{new_account.id}')['url'],
                         self.VERSIONED + '/sobjects/Account/@{new_account.id}')
        self.assertEqual(Composite.query('contacts', "SELECT Id FROM Contact WHERE AccountId = '@{new_account.id}'")['url'],
                         self.VERSIONED + '/query/?q=SELECT%20Id%20FROM%20Contact%20WHERE%20AccountId%20%3D%20'
                         '%27@{new_account.id}%27')

    def test_record_id_cannot_change_the_endpoint(self):
        self.assertEqual(Composite.delete('d', 'Account', '../../tooling/x?y=1')['url'],
                         self.VERSIONED + '/sobjects/Account/..%2F..%2Ftooling%2Fx%3Fy%3D1')

        with self.assertRaises(ValueError):
            Composite.delete('d', 'Account', '..')

    def test_api_version_can_be_overridden_at_runtime(self):
        with mock.patch.object(pysalesforceutils, 'API_VERSION', '60.0'):
            self.assertEqual(Composite.get('e', 'Account', '001A')['url'],
                             '/services/data/v60.0/sobjects/Account/001A')

    def test_builders_with_composite_request(self):
        subrequests = [Composite.create('new_account', 'Account', {'Name': 'Acme'}),
                       Composite.create('new_contact', 'Contact', {'LastName': 'Lee',
                                                                   'AccountId': '@{new_account.id}'})]

        Standard.composite_request(subrequests, True, TOKEN, INSTANCE)

        self.assert_request('POST', BASE + '/composite', {'allOrNone': True, 'collateSubrequests': True,
                                                          'compositeRequest': subrequests})

    def test_builders_with_composite_batch_request(self):
        subrequests = [Composite.update('u', 'Account', '001A', {'Name': 'Acme'}),
                       Composite.get('g', 'Account', '001A', 'Name')]
        version = 'v' + pysalesforceutils.API_VERSION

        Standard.composite_batch_request(subrequests, False, TOKEN, INSTANCE)

        self.assert_request('POST', BASE + '/composite/batch', {'haltOnError': False, 'batchRequests': [
            {'method': 'PATCH', 'url': version + '/sobjects/Account/001A', 'richInput': {'Name': 'Acme'}},
            {'method': 'GET', 'url': version + '/sobjects/Account/001A?fields=Name'}]})

    def test_builders_with_graph_composite_request(self):
        subrequests = [Composite.create('new_account', 'Account', {'Name': 'Acme'})]
        request_body = {'graphs': [Composite.graph('graph1', subrequests)]}

        Standard.graph_composite_request(request_body, TOKEN, INSTANCE)

        self.assert_request('POST', BASE + '/composite/graph',
                            {'graphs': [{'graphId': 'graph1', 'compositeRequest': subrequests}]})


class TestBulk2QueryJobs(MockedRequestTestCase):
    QUERY = BASE + '/jobs/query'

    def test_create_query_job(self):
        self.http_request.return_value.text = '{"id": "750A"}'

        result = Bulk2.create_query_job('SELECT Id FROM Account', False, TOKEN, INSTANCE)

        self.assertEqual(result, {'id': '750A'})
        self.assert_request('POST', self.QUERY, {'operation': 'query', 'query': 'SELECT Id FROM Account'})

    def test_create_query_all_job(self):
        Bulk2.create_query_job('SELECT Id FROM Account', True, TOKEN, INSTANCE)

        self.assert_request('POST', self.QUERY, {'operation': 'queryAll', 'query': 'SELECT Id FROM Account'})

    def test_get_query_job_info(self):
        Bulk2.get_query_job_info('750A', TOKEN, INSTANCE)

        self.assert_request('GET', self.QUERY + '/750A')

    def test_get_query_job_status_polls_until_finished(self):
        responses = []
        for state in ('UploadComplete', 'InProgress', 'JobComplete'):
            response = mock.Mock()
            response.text = json.dumps({'state': state, 'numberRecordsProcessed': 5})
            responses.append(response)
        self.http_request.side_effect = responses

        with mock.patch('time.sleep') as sleep:
            result = Bulk2.get_query_job_status('750A', 5, False, TOKEN, INSTANCE)

        self.assertEqual(result['state'], 'JobComplete')
        self.assertEqual(sleep.call_count, 2)

    def test_get_query_job_results(self):
        self.http_request.return_value.text = 'Id\n001A\n'
        self.http_request.return_value.headers = {'Sforce-Locator': 'MTAwMDA', 'Sforce-NumberOfRecords': '1'}

        result = Bulk2.get_query_job_results('750A', None, None, TOKEN, INSTANCE)

        self.assertEqual(result, {'records': 'Id\n001A\n', 'locator': 'MTAwMDA'})
        self.assert_request('GET', self.QUERY + '/750A/results', headers={'Accept': 'text/csv'})

    def test_get_query_job_results_last_page(self):
        self.http_request.return_value.text = 'Id\n001B\n'
        self.http_request.return_value.headers = {'Sforce-Locator': 'null'}

        result = Bulk2.get_query_job_results('750A', 'MTAwMDA', 1000, TOKEN, INSTANCE)

        self.assertEqual(result, {'records': 'Id\n001B\n', 'locator': None})
        self.assert_request('GET', self.QUERY + '/750A/results?locator=MTAwMDA&maxRecords=1000',
                            headers={'Accept': 'text/csv'})

    def test_abort_and_delete_query_job(self):
        Bulk2.abort_query_job('750A', TOKEN, INSTANCE)
        self.assert_request('PATCH', self.QUERY + '/750A', {'state': 'Aborted'})

        self.http_request.return_value.status_code = 204
        result = Bulk2.delete_query_job('750A', TOKEN, INSTANCE)

        self.assertEqual(result, 204)
        self.assert_request('DELETE', self.QUERY + '/750A')


class TestStandardOtherResources(MockedRequestTestCase):

    def test_get_global_describe_and_limits(self):
        Standard.get_global_describe(TOKEN, INSTANCE)
        self.assert_request('GET', BASE + '/sobjects')

        Standard.get_limits(TOKEN, INSTANCE)
        self.assert_request('GET', BASE + '/limits')

    def test_query_records_follows_every_batch(self):
        next_url = '/services/data/v' + pysalesforceutils.API_VERSION + '/query/01gxx-2000'
        responses = []
        for body in ({'done': False, 'nextRecordsUrl': next_url, 'records': [{'Id': '001A'}]},
                     {'done': True, 'records': [{'Id': '001B'}]}):
            response = mock.Mock()
            response.text = json.dumps(body)
            responses.append(response)
        self.http_request.side_effect = responses

        result = Standard.query_records('SELECT Id FROM Account', TOKEN, INSTANCE)

        self.assertEqual(result, [{'Id': '001A'}, {'Id': '001B'}])
        self.assertEqual([call.kwargs['URL'] for call in self.http_request.call_args_list],
                         [BASE + '/query/?q=SELECT%20Id%20FROM%20Account', INSTANCE + next_url])

    def test_query_records_can_include_deleted(self):
        self.http_request.return_value.text = '{"done": true, "records": []}'

        result = Standard.query_records('SELECT Id FROM Account', TOKEN, INSTANCE, include_deleted=True)

        self.assertEqual(result, [])
        self.assert_request('GET', BASE + '/queryAll/?q=SELECT%20Id%20FROM%20Account')

    def test_query_explain(self):
        Standard.query_explain('SELECT Id FROM Account', TOKEN, INSTANCE)

        self.assert_request('GET', BASE + '/query/?explain=SELECT%20Id%20FROM%20Account')

    def test_parameterized_search(self):
        search_body = {'q': 'Smith', 'fields': ['Id'], 'sobjects': [{'name': 'Contact'}]}

        Standard.parameterized_search(search_body, TOKEN, INSTANCE)

        self.assert_request('POST', BASE + '/parameterizedSearch', search_body)

    def test_invoke_actions(self):
        inputs = [{'accountId': '001A'}]

        Standard.invoke_standard_action('chatterPost', inputs, TOKEN, INSTANCE)
        self.assert_request('POST', BASE + '/actions/standard/chatterPost', {'inputs': inputs})

        Standard.invoke_custom_action('flow', 'My_Flow', inputs, TOKEN, INSTANCE)
        self.assert_request('POST', BASE + '/actions/custom/flow/My_Flow', {'inputs': inputs})

    def test_apex_rest_request_returns_the_response(self):
        result = Standard.apex_rest_request('POST', '/MyService/001A', TOKEN, INSTANCE, {'Name': 'Acme'})

        self.assertIs(result, self.http_request.return_value)
        self.assert_request('POST', INSTANCE + '/services/apexrest/MyService/001A', {'Name': 'Acme'})

    def test_request_returns_the_response(self):
        result = Standard.request('GET', '/sobjects/Account/describe', TOKEN, INSTANCE, headers={'X-Test': '1'})

        self.assertIs(result, self.http_request.return_value)
        self.assert_request('GET', BASE + '/sobjects/Account/describe', headers={'X-Test': '1'})


class TestToolingRecords(MockedRequestTestCase):
    SOBJECTS = BASE + '/tooling/sobjects'

    def test_get_sobject_row(self):
        self.http_request.return_value.text = '{"Id": "01pA"}'

        result = Tooling.get_sobject_row('ApexClass', '01pA', TOKEN, INSTANCE)

        self.assertEqual(result, {'Id': '01pA'})
        self.assert_request('GET', self.SOBJECTS + '/ApexClass/01pA')

    def test_create_sobject_row(self):
        self.http_request.return_value.text = '{"id": "7tfA", "success": true}'

        result = Tooling.create_sobject_row('TraceFlag', {'LogType': 'USER_DEBUG'}, TOKEN, INSTANCE)

        self.assertEqual(result, {'id': '7tfA', 'success': True})
        self.assert_request('POST', self.SOBJECTS + '/TraceFlag/', {'LogType': 'USER_DEBUG'})

    def test_update_and_delete_sobject_row(self):
        self.http_request.return_value.status_code = 204

        result = Tooling.update_sobject_row('TraceFlag', '7tfA', {'LogType': 'USER_DEBUG'}, TOKEN, INSTANCE)
        self.assertEqual(result, 'Update Successful')
        self.assert_request('PATCH', self.SOBJECTS + '/TraceFlag/7tfA', {'LogType': 'USER_DEBUG'})

        result = Tooling.delete_sobject_row('TraceFlag', '7tfA', TOKEN, INSTANCE)
        self.assertEqual(result, 'Delete Successful')
        self.assert_request('DELETE', self.SOBJECTS + '/TraceFlag/7tfA')


class TestPlans(MockedRequestTestCase):
    """
    The API methods are written as plans, which are generators that yield the
    requests they want sent. These tests cover the code that runs them.
    """

    def test_api_methods_keep_their_plan(self):
        self.assertTrue(inspect.isgeneratorfunction(Standard.query._plan))
        self.assertFalse(inspect.isgeneratorfunction(Standard.query))
        self.assertEqual(Standard.query.__doc__, Standard.query._plan.__doc__)

    def test_transport_errors_reach_the_caller(self):
        self.http_request.side_effect = RuntimeError('connection failed')

        with self.assertRaises(RuntimeError):
            Standard.query('SELECT Id FROM Account', TOKEN, INSTANCE)

    def test_error_in_a_nested_plan_reaches_the_caller(self):
        first = mock.Mock()
        first.text = '{"done": false, "nextRecordsUrl": "/next", "records": []}'
        self.http_request.side_effect = [first, RuntimeError('connection failed')]

        with self.assertRaises(RuntimeError):
            Standard.query_records('SELECT Id FROM Account', TOKEN, INSTANCE)

        self.assertEqual(self.http_request.call_count, 2)

    def test_a_plan_can_handle_an_error_and_continue(self):
        self.http_request.side_effect = [RuntimeError('connection failed'), mock.Mock(text='second')]

        def plan():
            try:
                yield util._Request(requestType='GET', URL=INSTANCE + '/first')
            except RuntimeError:
                response = yield util._Request(requestType='GET', URL=INSTANCE + '/second')
                return response.text

        self.assertEqual(util._run(plan()), 'second')

    def test_sleep_and_nested_plan_results(self):
        def inner():
            yield util._Sleep(3)
            return 'inner result'

        def plan():
            result = yield inner()
            return result

        with mock.patch('time.sleep') as sleep:
            self.assertEqual(util._run(plan()), 'inner result')

        sleep.assert_called_once_with(3)


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


class TestJwtBearerLogin(MockedRequestTestCase):
    LOGIN_RESPONSE = {'access_token': 'abc', 'instance_url': 'https://acme.my.salesforce.com'}

    INTROSPECT_RESPONSE = {'active': True, 'exp': 1800000000}

    def setUp(self):
        super().setUp()
        responses = []
        for body in (self.LOGIN_RESPONSE, self.INTROSPECT_RESPONSE):
            response = mock.Mock()
            response.text = json.dumps(body)
            responses.append(response)
        self.http_request.side_effect = responses

    def test_missing_library_raises_import_error(self):
        with mock.patch('pysalesforceutils.authentication.jwt', None):
            with self.assertRaises(ImportError) as context:
                Authentication.get_jwt_bearer_login('user@example.com', 'client id', 'client secret', 'key', True)

        self.assertIn('pysalesforceutils[jwt]', str(context.exception))
        self.http_request.assert_not_called()

    @unittest.skipIf(jwt is None, 'PyJWT[crypto] is not installed')
    def test_get_jwt_bearer_login(self):
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_key_pem = private_key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()

        for is_production, login_url in ((True, 'https://login.salesforce.com'),
                                         (False, 'https://test.salesforce.com')):
            with self.subTest(is_production=is_production):
                self.setUp()

                result = Authentication.get_jwt_bearer_login('user@example.com', 'client id', 'client secret',
                                                             private_key_pem, is_production)

                login_request, introspect_request = [call.kwargs for call in self.http_request.call_args_list]
                self.assertEqual(result, {'access_token': 'abc', 'instance_url': 'https://acme.my.salesforce.com',
                                          'exp': 1800000000})

                self.assertEqual(login_request['requestType'], 'POST')
                self.assertEqual(login_request['URL'], login_url + '/services/oauth2/token')
                self.assertEqual(login_request['data_body']['grant_type'],
                                 'urn:ietf:params:oauth:grant-type:jwt-bearer')

                # checks the signature, the audience and that it hasn't expired
                claims = jwt.decode(login_request['data_body']['assertion'], private_key.public_key(),
                                    algorithms=['RS256'], audience=login_url)
                self.assertEqual((claims['iss'], claims['sub']), ('client id', 'user@example.com'))
                self.assertLessEqual(claims['exp'] - time.time(), 180)

                # the token is introspected at the instance_url from the login response
                self.assertEqual(introspect_request['requestType'], 'POST')
                self.assertEqual(introspect_request['URL'],
                                 'https://acme.my.salesforce.com/services/oauth2/introspect')
                self.assertEqual(introspect_request['data_body'], {
                    'token': 'abc', 'token_type_hint': 'access_token', 'client_id': 'client id',
                    'client_secret': 'client secret'})

    def test_introspect_token(self):
        self.http_request.side_effect = None
        self.http_request.return_value.text = json.dumps(self.INTROSPECT_RESPONSE)

        result = Authentication.introspect_token('abc', 'client id', 'client secret', 'https://acme.my.salesforce.com')

        kwargs = self.http_request.call_args.kwargs
        self.assertEqual(result, self.INTROSPECT_RESPONSE)
        self.assertEqual(kwargs['URL'], 'https://acme.my.salesforce.com/services/oauth2/introspect')

        with self.assertRaises(ValueError):
            Authentication.introspect_token('abc', 'client id', 'client secret', 'http://acme.my.salesforce.com')

    def test_salesforce_login_jwt_bearer(self):
        login_response = dict(self.LOGIN_RESPONSE, exp=1800000000)

        with mock.patch.object(Authentication, 'get_jwt_bearer_login', return_value=login_response) as login:
            sf = Salesforce.login_jwt_bearer('user@example.com', 'client id', 'client secret', 'key', False)

        login.assert_called_once_with('user@example.com', 'client id', 'client secret', 'key', False)
        self.assertEqual((sf.access_token, sf.instance_url, sf.token_expiration),
                         ('abc', 'https://acme.my.salesforce.com', 1800000000))


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
        # the WSDL isn't read, so the client is created with the file name
        for patcher in (mock.patch('pysalesforceutils.util.Client'),
                        mock.patch('pysalesforceutils.util._load_wsdl', side_effect=lambda wsdl_file: wsdl_file),
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


WSDL_WITH_MISSING_TYPE = b"""<definitions xmlns="http://schemas.xmlsoap.org/wsdl/"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:tns="urn:test" targetNamespace="urn:test">
 <types>
  <xsd:schema targetNamespace="urn:test">
   <xsd:complexType name="Rule">
    <xsd:sequence>
     <xsd:element name="name" type="xsd:string"/>
     <xsd:element name="domain" type="tns:Domain"/>
    </xsd:sequence>
   </xsd:complexType>
  </xsd:schema>
 </types>
</definitions>"""


@unittest.skipIf(util.Client is None, 'zeep is not installed')
class TestWsdlLoading(unittest.TestCase):

    def schema_type_names(self, wsdl):
        from lxml import etree

        schema = etree.fromstring(wsdl.read()).find('.//{http://www.w3.org/2001/XMLSchema}schema')

        return [child.get('name') for child in schema]

    def test_missing_type_is_added(self):
        wsdl = util._load_wsdl(io.BytesIO(WSDL_WITH_MISSING_TYPE))

        self.assertEqual(self.schema_type_names(wsdl), ['Rule', 'Domain'])

    def test_complete_schema_is_not_changed(self):
        complete = WSDL_WITH_MISSING_TYPE.replace(b'type="tns:Domain"', b'type="xsd:string"')

        wsdl = util._load_wsdl(io.BytesIO(complete))

        self.assertEqual(self.schema_type_names(wsdl), ['Rule'])

    def test_bundled_wsdls_load(self):
        wsdl_files = (pysalesforceutils.METADATA_WSDL_FILE, pysalesforceutils.METADATA_SANDBOX_WSDL_FILE,
                      pysalesforceutils.PARTNER_WSDL_FILE, pysalesforceutils.PARTNER_SANDBOX_WSDL_FILE)

        with mock.patch.dict('pysalesforceutils.util._soap_clients', clear=True):
            for wsdl_file in wsdl_files:
                with self.subTest(wsdl_file=wsdl_file):
                    Util.get_soap_client(wsdl_file)

            service = Util.get_soap_client_service(pysalesforceutils.METADATA_WSDL_FILE,
                                                   pysalesforceutils.METADATA_SERVICE_BINDING,
                                                   INSTANCE + '/services/Soap/m/68.0')

        self.assertTrue(hasattr(service, 'deploy'))


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
