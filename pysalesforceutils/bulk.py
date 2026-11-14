#!/usr/bin/python3

"""
Salesforce Bulk API.
"""

import json
import time

import pysalesforceutils
from . import webservice
from .util import Util, _quote_path


class Bulk:
    """
    This class is used for doing bulk operations. Please use this and not the
    Standard class singular methods when you're performing DML operations. This
    is faster and will use fewer of your API calls.
    API details here: https://developer.salesforce.com/docs/atlas.en-us.api_asynch.meta/api_asynch/asynch_api_intro.htm
    examples here: https://trailhead-salesforce-com.firelayers.net/en/api_basics/api_basics_bulk
    Considerations here: https://developer.salesforce.com/docs/atlas.en-us.salesforce_app_limits_cheatsheet.meta/salesforce_app_limits_cheatsheet/salesforce_app_limits_platform_bulkapi.htm
    """
    base_bulk_uri = '/services/async/' + pysalesforceutils.API_VERSION
    batch_uri = '/job/'

    @staticmethod
    def get_job_status(job_id, polling_wait, verbose, access_token, instance_url):
        """
        This method is used for printing job status. If verbose = False, it will
        ignore the print statements.

        Args:
            job_id (str): The job id returned when creating a batch job
            polling_wait (int): This is the number of seconds
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            objects: Prints the status of the bulk job and polls for an update
                     ever polling_wait seconds until the numberBatchesQueued = 0,
                     then it will break out and just returns the final job status
                     response.
        """
        header_details = Util.get_bulk_header(access_token)

        if verbose:
            print("Status for job: {}".format(job_id))

        while True:
            response = webservice.Tools.get_http_response(
                instance_url + Bulk.base_bulk_uri + Bulk.batch_uri + _quote_path(job_id), header_details)
            json_response = json.loads(response.text)

            if verbose:
                print("Batches completed/failed/total: {}/{}/{}".format(json_response['numberBatchesCompleted'],
                                                                        json_response['numberBatchesFailed'],
                                                                        json_response['numberBatchesTotal']))

            total_jobs_run = json_response['numberBatchesCompleted'] + json_response['numberBatchesFailed']
            if total_jobs_run == json_response['numberBatchesTotal']:
                break
            elif json_response.get('state') in ('Aborted', 'Failed'):
                # the remaining batches will never be processed
                break
            else:
                time.sleep(polling_wait)

        return json_response

    @staticmethod
    def get_batch_result(job_id, batch_id, access_token, instance_url):
        """
        This method will retrieve the results of a batch operation.

        Args:
            job_id (str): The job id returned when creating a batch job
            batch_id (str): This is the batch Id returned when creating a new
                            batch
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            array: Returns the an array containing the results for each record
                   in the given batch
        """
        header_details = Util.get_bulk_header(access_token)

        response = webservice.Tools.get_http_response(
            instance_url + Bulk.base_bulk_uri + Bulk.batch_uri + _quote_path(job_id) + '/batch/' +
            _quote_path(batch_id) + '/result',
            header_details)
        json_response = json.loads(response.text)

        return json_response

    @staticmethod
    def get_query_result(job_id, batch_id, query_result_id, access_token, instance_url):
        """
        This method will retrieve the results of a batch operation.

        Args:
            job_id (str): The job id returned when creating a batch job
            batch_id (str): This is the batch Id returned when creating a new
                            batch
            query_result_id (str): Ths is the Id returned with a successful
                                   batch for a Salesforce bulk query.
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            array: Returns the an array containing the results for the query
                   request
        """
        header_details = Util.get_bulk_header(access_token)

        response = webservice.Tools.get_http_response(
            instance_url + Bulk.base_bulk_uri + Bulk.batch_uri + _quote_path(job_id) + '/batch/' +
            _quote_path(batch_id) + '/result' + '/' + _quote_path(query_result_id),
            header_details)
        json_response = json.loads(response.text)

        return json_response

    @staticmethod
    def perform_bulk_operation(object_api_name, records, batch_size, operation_type, polling_wait,
                               external_id_field_name, access_token, instance_url, concurrency_mode=None,
                               verbose=True):
        """
        This method updates a list of records provided as an object.

        Args:
            object_api_name (str): The API Name of the object being updated
            records (array): The list of records that needs to be updated. This
                             Should be provided as an array. For example:
                             [{'id':'recordId', 'phone':'(123) 456-7890'}]
            batch_size (int): This is the batch size of the records to process.
                              If you were to pass 5000 records into the process
                              with a batch size of 1000, then there would be 5
                              batches processed.
            operation_type (str): This is the operation being performed: delete,
                                  insert, query, upsert, update, hardDelete
            polling_wait (int): This is the number of seconds to wait between
                                each poll for updates on the job
            external_id_field_name (str): This is the external Id field that is
                                          used to determine whether this record
                                          will be inserted or updated. This is
                                          required for upserts, but will default
                                          to the record Id field
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response
            concurrency_mode (str): Can't update after creation. The concurrency
                                    mode for the job. The valid values are:
                                    Parallel: Process batches in parallel mode.
                                              This is the default value.
                                    Serial: Process batches in serial mode.
                                            Processing in parallel can cause
                                            database contention. When this is
                                            severe, the job may fail. If
                                            you're experiencing this issue,
                                            submit the job with serial
                                            concurrency mode. This guarantees
                                            that batches are processed one at
                                            a time. Note that using this
                                            option may significantly increase
                                            the processing time for a job.

        Returns:
            object: Returns an object containing the status for each record that
                    was put into the batch
        """
        header_details = Util.get_bulk_header(access_token)
        body_details = {}

        if external_id_field_name != None:
            body_details = Util.get_bulk_job_body(object_api_name, operation_type, None, concurrency_mode,
                                                  external_id_field_name)
        else:
            body_details = Util.get_bulk_job_body(object_api_name, operation_type, None, concurrency_mode)

        chunked_records_list = Util.chunk(records, batch_size)
        batch_ids = []
        results_list = []

        # create the bulk job
        create_job_json_body = json.dumps(body_details, indent=4, separators=(',', ': '))
        job_create_response = webservice.Tools.post_http_response(instance_url + Bulk.base_bulk_uri + Bulk.batch_uri,
                                                                  create_job_json_body, header_details)
        json_job_create_response = json.loads(job_create_response.text)
        job_id = json_job_create_response['id']

        # loop through the record batches, and add them to the processing queue
        for record_chunk in chunked_records_list:
            records_json = json.dumps(record_chunk, indent=4, separators=(',', ': '))
            job_batch_response = webservice.Tools.post_http_response(
                instance_url + Bulk.base_bulk_uri + Bulk.batch_uri + job_id + '/batch', records_json,
                header_details)
            json_job_batch_response = json.loads(job_batch_response.text)
            batch_id = json_job_batch_response['id']
            batch_ids.append(batch_id)

        # close the bulk job
        close_body = {'state': 'Closed'}
        json_close_body = json.dumps(close_body, indent=4, separators=(',', ': '))
        close_response = webservice.Tools.post_http_response(
            instance_url + Bulk.base_bulk_uri + Bulk.batch_uri + job_id, json_close_body, header_details)
        json_close_response = json.loads(close_response.text)

        # set default job check polling to 5 seconds
        if polling_wait is None:
            polling_wait = 5

        # check job status until the job completes
        Bulk.get_job_status(job_id, polling_wait, verbose, access_token, instance_url)

        # populate the results_list by appending the results of each batch
        for this_batch_id in batch_ids:
            batch_results = Bulk.get_batch_result(job_id, this_batch_id, access_token, instance_url)
            results_list.extend(batch_results)

        return results_list

    @staticmethod
    def insert_sobject_rows(object_api_name, records, batch_size, polling_wait, access_token, instance_url,
                            concurrency_mode=None):
        """
        This method inserts a list of records provided as an object.

        Args:
            object_api_name (str): The API Name of the object being updated
            records (array): The list of records that needs to be updated. This
                             Should be provided as an array. For example:
                             [{'id':'recordId', 'phone':'(123) 456-7890'}]
            batch_size (int): This is the batch size of the records to process.
                              If you were to pass 5000 records into the process
                              with a batch size of 1000, then there would be 5
                              batches processed.
            polling_wait (int): This is the number of seconds to wait between
                                each poll for updates on the job
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                               login response
            concurrency_mode (str): Can't update after creation. The concurrency
                                    mode for the job. The valid values are:
                                    Parallel: Process batches in parallel mode.
                                              This is the default value.
                                    Serial: Process batches in serial mode.
                                            Processing in parallel can cause
                                            database contention. When this is
                                            severe, the job may fail. If
                                            you're experiencing this issue,
                                            submit the job with serial
                                            concurrency mode. This guarantees
                                            that batches are processed one at
                                            a time. Note that using this
                                            option may significantly increase
                                            the processing time for a job.
        Returns:
            object: Returns an object containing the status for each record that
                    was put into the batch
        """
        result = Bulk.perform_bulk_operation(object_api_name, records, batch_size, 'insert', polling_wait, None,
                                             access_token, instance_url, concurrency_mode)

        return result

    @staticmethod
    def update_sobject_rows(object_api_name, records, batch_size, polling_wait, access_token, instance_url,
                            concurrency_mode=None):
        """
        This method updates a list of records provided as an object.

        Args:
            object_api_name (str): The API Name of the object being updated
            records (array): The list of records that needs to be updated. This
                             Should be provided as an array. For example:
                             [{'id':'recordId', 'phone':'(123) 456-7890'}]
            batch_size (int): This is the batch size of the records to process.
                              If you were to pass 5000 records into the process
                              with a batch size of 1000, then there would be 5
                              batches processed.
            polling_wait (int): This is the number of seconds to wait between
                                each poll for updates on the job
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response
            concurrency_mode (str): Can't update after creation. The concurrency
                                    mode for the job. The valid values are:
                                    Parallel: Process batches in parallel mode.
                                              This is the default value.
                                    Serial: Process batches in serial mode.
                                            Processing in parallel can cause
                                            database contention. When this is
                                            severe, the job may fail. If
                                            you're experiencing this issue,
                                            submit the job with serial
                                            concurrency mode. This guarantees
                                            that batches are processed one at
                                            a time. Note that using this
                                            option may significantly increase
                                            the processing time for a job.
        Returns:
            object: Returns an object containing the status for each record that
                    was put into the batch
        """
        result = Bulk.perform_bulk_operation(object_api_name, records, batch_size, 'update', polling_wait, None,
                                             access_token, instance_url, concurrency_mode)

        return result

    @staticmethod
    def upsert_sobject_rows(object_api_name, records, batch_size, polling_wait, access_token, instance_url,
                            external_id_field_name='Id', concurrency_mode=None):
        """
        This method upserts a list of records provided as an object.

        Args:
            object_api_name (str): The API Name of the object being updated
            records (array): The list of records that needs to be updated. This
                             Should be provided as an array. For example:
                             [{'id':'recordId', 'phone':'(123) 456-7890'}]
            batch_size (int): This is the batch size of the records to process.
                              If you were to pass 5000 records into the process
                              with a batch size of 1000, then there would be 5
                              batches processed.
            polling_wait (int): This is the number of seconds to wait between
                                each poll for updates on the job
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response
            external_id_field_name (str): This is the external Id field that is
                                          used to determine whether this record
                                          will be inserted or updated. This is
                                          required for upserts, but will default
                                          to the record Id field
            concurrency_mode (str): Can't update after creation. The concurrency
                                    mode for the job. The valid values are:
                                    Parallel: Process batches in parallel mode.
                                              This is the default value.
                                    Serial: Process batches in serial mode.
                                            Processing in parallel can cause
                                            database contention. When this is
                                            severe, the job may fail. If
                                            you're experiencing this issue,
                                            submit the job with serial
                                            concurrency mode. This guarantees
                                            that batches are processed one at
                                            a time. Note that using this
                                            option may significantly increase
                                            the processing time for a job.
        Returns:
            @return               Returns an object containing the status for each
                                  record that was put into the batch
        """
        result = Bulk.perform_bulk_operation(object_api_name, records, batch_size, 'upsert', polling_wait,
                                             external_id_field_name, access_token, instance_url, concurrency_mode)

        return result

    @staticmethod
    def delete_sobject_rows(object_api_name, records, hard_delete, batch_size, polling_wait, access_token,
                            instance_url):
        """
        This method upserts a list of records provided as an object.

        Args:
            object_api_name (str): The API Name of the object being updated
            records (array): The list of records that needs to be updated. This
                             Should be provided as an array. For example:
                             [{'id':'recordId', 'phone':'(123) 456-7890'}]
            hard_delete (bool): This Bool indicates whether or not the record
                                should be hard deleted. NOTE: There is a profile
                                System Permission option called "Bulk API Hard
                                Delete" that must be enabled for this option to
                                work.
            batch_size (int): This is the batch size of the records to process.
                              If you were to pass 5000 records into the process
                              with a batch size of 1000, then there would be 5
                              batches processed.
            polling_wait (int): This is the number of seconds to wait between
                                each poll for updates on the job
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            object: Returns an object containing the status for each record that
                    was put into the batch
        """
        delete_type = 'delete'

        if hard_delete:
            delete_type = 'hardDelete'

        result = Bulk.perform_bulk_operation(object_api_name, records, batch_size, delete_type, polling_wait, None,
                                             access_token, instance_url)

        return result

    @staticmethod
    def query_sobject_rows(object_api_name, query, query_all, access_token, instance_url, verbose=True):
        """
        This returns the result for a bulk query operations.

        Args:
            object_api_name (str): The API Name of the object being updated
            query (str): The query you'd like to run to retrieve records
            query_all (bool): State whether or not this query should query all
                              records (so you can get deleted records)
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            object: Returns an array of results for the specified query
        """
        header_details = Util.get_bulk_header(access_token)
        batch_results_list = []
        query_result_list = []

        query_type = 'query'

        if query_all:
            query_type = 'queryAll'

        # create the bulk job
        job_body_details = Util.get_bulk_job_body(object_api_name, query_type, None, None)
        create_job_json_body = json.dumps(job_body_details, indent=4, separators=(',', ': '))
        job_create_response = webservice.Tools.post_http_response(instance_url + Bulk.base_bulk_uri + Bulk.batch_uri,
                                                                  create_job_json_body, header_details)
        json_job_create_response = json.loads(job_create_response.text)
        job_id = json_job_create_response['id']

        # create the query request batch
        job_batch_response = webservice.Tools.post_http_response(
            instance_url + Bulk.base_bulk_uri + Bulk.batch_uri + job_id + '/batch', query, header_details)
        json_job_batch_response = json.loads(job_batch_response.text)
        batch_id = json_job_batch_response['id']

        # close the bulk job
        close_body = {'state': 'Closed'}
        json_close_body = json.dumps(close_body, indent=4, separators=(',', ': '))
        close_response = webservice.Tools.post_http_response(
            instance_url + Bulk.base_bulk_uri + Bulk.batch_uri + job_id, json_close_body, header_details)
        json_close_response = json.loads(close_response.text)

        # check job status until the job completes
        Bulk.get_job_status(job_id, 5, verbose, access_token, instance_url)

        # get results
        batch_results = Bulk.get_batch_result(job_id, batch_id, access_token, instance_url)
        batch_results_list.extend(batch_results)

        for query_result_id in batch_results_list:
            query_result = Bulk.get_query_result(job_id, batch_id, query_result_id, access_token, instance_url)
            query_result_list.extend(query_result)

        return query_result_list
