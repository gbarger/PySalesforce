#!/usr/bin/python3
import datetime
import json
import unittest
from unittest import mock

import pysalesforceutils
from pysalesforceutils import Standard, Bulk, Bulk2, Metadata

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


class TestStandard(MockedRequestTestCase):

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


class TestBulkPolling(MockedRequestTestCase):

    def setUp(self):
        super().setUp()
        patcher = mock.patch('pysalesforceutils.time.sleep')
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
