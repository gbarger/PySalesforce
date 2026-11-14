#!/usr/bin/python3

"""
Salesforce Bulk API 2.0.
"""

import time

import pysalesforceutils
from .util import _quote_path, _rest_json, _rest_request

_INGEST_URI = '/jobs/ingest'


class Bulk2:
    """
    Bulk API 2.0 provides a simple interface for quickly loading large amounts
    of data into your Salesforce org. Currently csv is the only supported format.

    https://developer.salesforce.com/docs/atlas.en-us.api_bulk_v2.meta/api_bulk_v2/introduction_bulk_api_2.htm
    """
    # no longer used by the methods in this class. Kept so existing code that
    # reads it doesn't break.
    base_bulk2_uri = '/services/data/v' + pysalesforceutils.API_VERSION + '/jobs/ingest'

    @staticmethod
    def get_job_list(is_pk_chunking_enabled, job_type, query_locator, access_token, instance_url):
        """
        Retrieves all jobs in the org.

        Args:
            is_pk_chunking_enabled (bool): If set to true, filters jobs with PK
                                           chunking enabled.
            job_type (str): Filters jobs based on job type. Valid values include:
                            BigObjectIngest—BigObjects job
                            Classic—Bulk API 1.0 job
                            V2Ingest—Bulk API 2.0 job
            query_locator (int): Use queryLocator with a locator value to get a
                                 specific set of job results. Get All Jobs returns
                                 up to 1000 result rows per request, along with
                                 a nextRecordsUrl value that contains the locator
                                 value used to get the next set of results.

        Returns:
            dict: Object containing a list of every job and the details of the
                  jobs.
                  done (bool): Indicates whether there are more jobs to get. If
                               false, use the nextRecordsUrl value to retrieve
                               the next group of jobs.
                  records (dict): The same details of the job that can be
                                  retrieved with the get_job_info.
                  nextRecordsUrl (str): A URL that contains a query locator used
                                        to get the next set of results in a
                                        subsequent request if done isn’t true.
        """
        uri_params = []
        uri_param_string = ""

        if is_pk_chunking_enabled:
            uri_params.append("isPkChunkingEnabled=true")

        if job_type:
            uri_params.append("jobType=" + _quote_path(job_type))

        if query_locator:
            uri_params.append("queryLocator=" + _quote_path(str(query_locator)))

        if uri_params:
            uri_param_string = "?" + "&".join(uri_params)

        json_response = _rest_json('GET', _INGEST_URI + uri_param_string, access_token, instance_url)

        return json_response

    @staticmethod
    def create_job(object_name, operation, external_id_field_name, column_delimiter, content_type, line_ending,
                   access_token, instance_url):
        """
        Creates a job, which represents a bulk operation (and associated data)
        that is sent to Salesforce for asynchronous processing. Provide job data
        via an Upload Job Data request, or as part of a multipart create job
        request.

        Args:
            object_name (str): Required. The object type for the data being
                               processed. Use only a single object type per job.
            operation (str): Required. The processing operation for the job.
                             Valid values are:
                                insert
                                delete
                                update
                                upsert
            external_id_field_name (str): Required for upsert operations. The
                                          external ID field in the object being
                                          updated. Only needed for upsert
                                          operations. Field values must also
                                          exist in CSV job data.
            column_delimiter (str): Optional. The column delimiter used for CSV
                                    job data. The default value is COMMA. Valid
                                    values are:
                                        BACKQUOTE—backquote character (`)
                                        CARET—caret character (^)
                                        COMMA—comma character (,) which is the
                                            default delimiter
                                        PIPE—pipe character (|)
                                        SEMICOLON—semicolon character (;)
                                        TAB—tab character
            content_type (str): Optional. The content type for the job. The only
                                valid value (and the default) is CSV.
            line_ending (str): Optional. The line ending used for CSV job data,
                               marking the end of a data row. The default is LF.
                               Valid values are:
                                    LF—linefeed character
                                    CRLF—carriage return character followed by a
                                        linefeed character
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            dict: Returns data about the job. The "id" field provides the job Id
                  necessary for the remaining calls. Create job response details:
                  https://developer.salesforce.com/docs/atlas.en-us.api_bulk_v2.meta/api_bulk_v2/create_job.htm
        """
        headers = {"Content-Type": "application/json; charset=UTF-8", "Accept": "application/json"}

        post_body = {}
        post_body["object"] = object_name
        post_body["operation"] = operation

        if external_id_field_name:
            post_body["externalIdFieldName"] = external_id_field_name

        if column_delimiter:
            post_body["columnDelimiter"] = column_delimiter

        if content_type:
            post_body["contentType"] = content_type

        if line_ending:
            post_body["lineEnding"] = line_ending

        json_response = _rest_json('POST', _INGEST_URI, access_token, instance_url, post_body, headers)

        return json_response

    @staticmethod
    def upload_csv_batch(data_set, job_id, access_token, instance_url):
        """
        Uploads data for a job using CSV data you provide.

        Args:
            data_set (str): This is a base64 encoded csv set.
            job_id (str): This is the job id from the Bulk2.create_job response.
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response.

        Returns:
            int: Returns the status code. If the upload was successful, the
                 response code should be 201.
        """
        headers = {"Content-Type": "text/csv", "Accept": "application/json"}

        response = _rest_request('PUT', _INGEST_URI + '/' + _quote_path(job_id) + '/batches', access_token,
                                 instance_url, data_set, headers)

        return response.status_code

    @staticmethod
    def change_job_state(job_state, job_id, access_token, instance_url):
        """
        Closes or aborts a job. If you close a job, Salesforce queues the job
        and uploaded data for processing, and you can’t add any additional job
        data. If you abort a job, the job does not get queued or processed.

        Args:
            job_state (str): The state to update the job to. Use UploadComplete
                             to close a job, or Aborted to abort a job.
            job_id (str): The job id returned by Bulk2.create_job
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response.

        Returns:
            dict: Returns the current job state details.
        """
        request_body = {"state": job_state}

        json_response = _rest_json('PATCH', _INGEST_URI + '/' + _quote_path(job_id), access_token, instance_url,
                                   request_body)

        return json_response

    @staticmethod
    def delete_job(job_id, access_token, instance_url):
        """
        Deletes a job. To be deleted, a job must have a state of UploadComplete,
        JobComplete, Aborted, or Failed.

        Args:
            job_id (str): The job id returned by Bulk2.create_job
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response.

        Returns:
            int: Returns the http status code. Should be 204 which indicates the
                 job was deleted successfully.
        """
        response = _rest_request('DELETE', _INGEST_URI + '/' + _quote_path(job_id), access_token, instance_url)

        return response.status_code

    @staticmethod
    def get_job_info(job_id, access_token, instance_url):
        """
        Retrieves detailed information about a job.

        Args:
            job_id (str): The job id returned by Bulk2.create_job
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response.

        Returns:
            dict: Returns details about the status of the given job. If the job
                  succeeds, the status will be 'JobComplete' vs 'Failed' for
                  a failed job. More details here:
                  https://developer.salesforce.com/docs/atlas.en-us.api_bulk_v2.meta/api_bulk_v2/get_job_info.htm
        """
        json_response = _rest_json('GET', _INGEST_URI + '/' + _quote_path(job_id), access_token, instance_url)

        return json_response

    @staticmethod
    def get_job_status(job_id, polling_wait, verbose, access_token, instance_url):
        """
        This method is used for printing job status. If verbose is False it will
        still wait but ignore the print statements.

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
        if verbose:
            print("Status for job: {}".format(job_id))

        processed_total = 0
        finished_statuses = ['JobComplete', 'Aborted', 'Failed']
        while True:
            json_response = Bulk2.get_job_info(job_id, access_token, instance_url)

            if verbose:
                print("Job state/failed/total: {}/{}/{}".format(json_response['state'],
                                                                json_response['numberRecordsFailed'],
                                                                json_response['numberRecordsProcessed']))

            if json_response['state'] in finished_statuses:
                #Bulk v2 will set status to Failed even while the job is processing if it encounters a record
                #failure, checking to see if records processes has not moved since the last poll
                if json_response['state'] != 'Failed' or processed_total == json_response['numberRecordsProcessed']:
                    break

            processed_total = json_response['numberRecordsProcessed']
            time.sleep(polling_wait)

        return json_response

    @staticmethod
    def get_success_results(job_id, access_token, instance_url):
        """
        Retrieves a list of successfully processed records for a completed job.

        Args:
            job_id (str): The job id returned by Bulk2.create_job
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response.

        Returns:
            str: Returns a CSV with 2 columns at the start, then all the fields
                 that were originally sent.
                 sf__Created (bool): Indicates if the record was created.
                 sf__Id (str): ID of the record that was successfully processed.
        """
        response = _rest_request('GET', _INGEST_URI + '/' + _quote_path(job_id) + '/successfulResults/', access_token,
                                 instance_url)

        return response.text

    @staticmethod
    def get_failed_results(job_id, access_token, instance_url):
        """
        Retrieves a list of failed records for a completed job.

        Args:
            job_id (str): The job id returned by Bulk2.create_job
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response.

        Returns:
            str: Returns a CSV with 2 columns at the start, then all the fields
                 that were originally sent.
                 sf__Error (str): Error code and message, if applicable.
                 sf__Id (str): ID of the record that had an error during
                               processing, if applicable.
        """
        response = _rest_request('GET', _INGEST_URI + '/' + _quote_path(job_id) + '/failedResults/', access_token,
                                 instance_url)

        return response.text

    @staticmethod
    def get_unprocessed_results(job_id, access_token, instance_url):
        """
        Retrieves a list of unprocessed records for a completed job.

        Args:
            job_id (str): The job id returned by Bulk2.create_job
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response.

        Returns:
            str: Returns a CSV with all the fields that were originally supplied.
        """
        response = _rest_request('GET', _INGEST_URI + '/' + _quote_path(job_id) + '/unprocessedrecords/', access_token,
                                 instance_url)

        return response.text
