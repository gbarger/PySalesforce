#!/usr/bin/python3

"""
Utilities reused by the other modules in this package.
"""

import json
import urllib.parse

import pysalesforceutils
from . import webservice

try:
    from zeep import Client
except ImportError:
    Client = None


def _quote_path(value):
    """
    URL encodes a value so it can only ever be a single URL path segment or
    query value, and can't change which endpoint is called.
    """
    if value in ('.', '..'):
        raise ValueError('Invalid URL path value: {}'.format(value))

    return urllib.parse.quote(value, safe='')


def _encode_body(data):
    """
    Turns a python object into a JSON request body. A str or bytes value is
    returned as is, and None means there is no body.
    """
    if data is None or isinstance(data, (str, bytes)):
        return data

    return json.dumps(data)


def _rest_request(method, path, access_token, instance_url, data=None, headers=None):
    """
    Sends a request to the Salesforce REST API for the current API_VERSION.

    Args:
        method (str): The request type: GET, POST, PATCH, PUT or DELETE
        path (str): The part of the URL that comes after /services/data/vXX.X
        access_token (str): This is the access_token value received from the
                            login response
        instance_url (str): This is the instance_url value received from the
                            login response
        data (object): A python object to send as the JSON request body. A
                       str or bytes value is sent as is. Defaults to None
        headers (dict): Headers to add to the standard header. Defaults to None

    Returns:
        Response: Returns the response for the HTTP request.
    """
    header_details = Util.get_standard_header(access_token)

    if headers != None:
        header_details.update(headers)

    url = instance_url + '/services/data/v' + pysalesforceutils.API_VERSION + path

    return webservice.Tools.http_request(requestType=method, URL=url, data_body=_encode_body(data),
                                         header_details=header_details)


def _rest_json(method, path, access_token, instance_url, data=None, headers=None):
    """
    Does the same as _rest_request, but returns the parsed JSON response body.
    """
    response = _rest_request(method, path, access_token, instance_url, data, headers)

    return json.loads(response.text)


class Util:
    """
    This is a collection of utilities that will need to be reused by the methods
    within the classes.
    """

    @staticmethod
    def get_standard_header(access_token):
        """
        This method will be used to generated headers. The documentation shows
        that there are header options availble, but doesn't do a good job of
        explaining what they're for or what they do, so I'm leaving this here to
        generate the headers. For now it will just be a static header with the
        access_token and X-PrettyPrint.

        Args:
            access_token (str): This is the access_token value received from
                                the login response

        Returns:
            object: Returns a header that has the required values for the
                    standard API.
        """
        object_header = {"Authorization": "Bearer " + access_token, "Content-Type": "application/json"}
        return object_header

    @staticmethod
    def get_bulk_header(access_token):
        """
        This method builds the header for bulk requests using the access_token

        Args:
            access_token (str): This is the access_token value received from
                                the login response

        Returns:
            object: Returns a header that has the required values for the bulk
                    API. Namely, this takes the standard header and adds gzip
                    encoding, which is recommended by Salesforce to reduce the
                    size of the responses. This works because requests will
                    automatically unzip the zipped responses.
        """
        bulk_header = Util.get_standard_header(access_token)
        bulk_header['X-SFDC-Session'] = access_token
        # bulkHeader['Content-Encoding'] = 'gzip'
        return bulk_header

    @staticmethod
    def get_bulk_job_body(object_api_name, operation_type, assignment_rule_id=None, concurrency_mode=None,
                          external_id_field_name=None, number_retries=None, job_state=None):
        """
        This method will be used to generate the bulk job body that is then used
        to send operation batches to Salesforce for processing.

        Args:
            object_api_name (str): REQUIRED: The object name this job will
                                   perform operations on
            operation_type (str): REQUIRED: This is the type of operation that
                                  will be run with this request. Possible
                                  values include: delete, insert, query,
                                  upsert, update, and hardDelete
            assignment_rule_id (str): The ID of a specific assignment rule to
                                      run for a case or a lead. The assignment
                                      rule can be active or inactive.
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
            external_id_field_name (str): REQUIRED WITH UPSERT. The name of
                                          the external ID field for an
                                          upsert().
            number_retries (int): The number of times that Salesforce attempted
                                  to save the results of an operation. The
                                  repeated attempts are due to a problem,
                                  such as a lock contention.
            job_state (str): REQUIRED IF CREATING, CLOSING OR ABORTING A JOB.
                             The current state of processing for the job:
                             Values:
                             Open: The job has been created, and batches
                                 can be added to the job.
                             Closed: No new batches can be added to this
                                 job. Batches associated with the job may
                                 be processed after a job is closed. You
                                 cannot edit or save a closed job.
                             Aborted: The job has been aborted. You can
                                 abort a job if you created it or if you
                                 have the “Manage Data Integrations”
                                 permission.
                             Failed: The job has failed. Batches that were
                                 successfully processed can't be rolled back.
                                 The BatchInfoList contains a list of all
                                 batches for the job. From the results of
                                 BatchInfoList, results can be retrieved
                                 for completed batches. The results indicate
                                 which records have been processed. The
                                 numberRecordsFailed field contains the
                                 number of records that were not processed
                                 successfully.

        Returns:
            object: This returns the body formatted for a bulk job
        """
        bulk_job_body = {'operation': operation_type, 'object': object_api_name, 'contentType': 'JSON'}

        if assignment_rule_id != None:
            bulk_job_body['assignmentRuleId'] = assignment_rule_id

        if concurrency_mode != None:
            bulk_job_body['concurrencyMode'] = concurrency_mode

        if external_id_field_name != None:
            bulk_job_body['externalIdFieldName'] = external_id_field_name

        if number_retries != None:
            bulk_job_body['numberRetries'] = number_retries

        if job_state != None:
            bulk_job_body['state'] = job_state

        return bulk_job_body

    @staticmethod
    def chunk(list, n):
        """
        This generator breaks up a list into a list of lists that contains n
        items in each list.

        Args:
            list (array): The list provided to be chunked
            n (int): The number of items in each chunk

        Returns:
            Array of Arrays: This returns a list of lists which is the original
            list chunked into pieces of size n
        """
        for i in range(0, len(list), n):
            yield list[i:i + n]

    @staticmethod
    def get_soap_client(wsdl_file):
        """
        Pass the wsdl and generate the soap client for the given WSDL

        Args:
            wsdl_file (str): The file location for the WSDL used to generate
                             the client

        Returns:
            Client: Returns the SOAP client.
        """
        if Client is None:
            raise ImportError(
                "The 'zeep' library is required to use the Metadata or SOAP APIs. "
                "Install it using `pip install zeep` or `pip install pysalesforceutils[soap]`."
            )

        soap_client = Client(wsdl_file)
        return soap_client

    @staticmethod
    def get_soap_client_service(wsdl_file, service_binding, endpoint_url):
        """
        This method takes the given arguments and creates the soap client service.

        Args:
            wsdl_file (str): The file location for the WSDL used to generate
                             the client.
            service_binding (str): The name of the service binding to create
            endpoint_url (str): The endpoint url to call for the service binding

        Returns:
            client_service: Returns the SOAP client service.
        """
        soap_client = Util.get_soap_client(wsdl_file)
        soap_client_service = soap_client.create_service(service_binding, endpoint_url)

        return soap_client_service
