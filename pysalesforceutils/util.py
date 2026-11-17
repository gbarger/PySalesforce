#!/usr/bin/python3

"""
Utilities reused by the other modules in this package.
"""

import asyncio
import functools
import io
import json
import time
import urllib.parse

import pysalesforceutils
from . import webservice

try:
    from zeep import Client
except ImportError:
    Client = None


# SOAP clients that have already been loaded, by WSDL file
_soap_clients = {}


def _load_wsdl(wsdl_file):
    """
    Reads a WSDL file so it can be passed to zeep. Some WSDLs that Salesforce
    generates refer to types they never define, e.g. the v68 Metadata WSDL
    uses PolicyRulePrincipalDomain for the PolicyRule metadata type. zeep
    can't load a WSDL like that, so each missing type is added here as a type
    that accepts any content. The file itself is not changed.

    Args:
        wsdl_file (str): The file location for the WSDL

    Returns:
        io.BytesIO: Returns the WSDL, with any missing types added.
    """
    # lxml is installed with zeep, so it's only needed when zeep is
    from lxml import etree

    xsd = 'http://www.w3.org/2001/XMLSchema'
    tree = etree.parse(wsdl_file)

    for schema in tree.iter('{' + xsd + '}schema'):
        target_namespace = schema.get('targetNamespace')
        defined = {child.get('name') for child in schema if child.get('name')}
        missing = set()

        for element in schema.iter():
            for attribute in ('type', 'base'):
                value = element.get(attribute)

                if value and ':' in value:
                    prefix, name = value.split(':', 1)

                    if element.nsmap.get(prefix) == target_namespace and name not in defined:
                        missing.add(name)

        for name in sorted(missing):
            complex_type = etree.SubElement(schema, '{' + xsd + '}complexType', name=name)
            sequence = etree.SubElement(complex_type, '{' + xsd + '}sequence')
            etree.SubElement(sequence, '{' + xsd + '}any', minOccurs='0', maxOccurs='unbounded',
                             processContents='lax')

    return io.BytesIO(etree.tostring(tree))


def _quote_path(value):
    """
    URL encodes a value so it can only ever be a single URL path segment or
    query value, and can't change which endpoint is called.
    """
    if value in ('.', '..'):
        raise ValueError('Invalid URL path value: {}'.format(value))

    return urllib.parse.quote(value, safe='')


class _Request:
    """
    Describes an HTTP request for an API method to send. The keyword
    arguments are the same as the ones for webservice.Tools.http_request.
    """

    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _Sleep:
    """
    Tells the code running an API method to wait before continuing.
    """

    def __init__(self, seconds):
        self.seconds = seconds


def _run(plan):
    """
    Runs an API method that was written as a plan. A plan is a generator that
    yields each thing it needs done and is sent back the result:
        yield _Request(...)     sends the request, the result is the response
        yield _Sleep(seconds)   waits
        yield another_plan      runs it, the result is what that plan returns

    Writing the methods this way means the same method can be run here, where
    each request blocks until it's done, or asynchronously.
    """
    try:
        step = next(plan)

        while True:
            try:
                if isinstance(step, _Request):
                    result = webservice.Tools.http_request(**step.kwargs)
                elif isinstance(step, _Sleep):
                    result = time.sleep(step.seconds)
                else:
                    result = _run(step)
            except Exception as error:
                # let the plan handle the error the same way it would if it
                # had made the request itself
                step = plan.throw(error)
            else:
                step = plan.send(result)
    except StopIteration as finished:
        return finished.value


async def _run_async(plan, client):
    """
    Runs an API method that was written as a plan, the same way _run does,
    but sends the requests with an httpx.AsyncClient and waits with
    asyncio.sleep, so other tasks can run in the meantime.

    Args:
        plan (generator): The plan to run
        client (httpx.AsyncClient): The client to send the requests with
    """
    try:
        step = next(plan)

        while True:
            try:
                if isinstance(step, _Request):
                    result = await webservice.Tools.async_http_request(client, **step.kwargs)
                elif isinstance(step, _Sleep):
                    result = await asyncio.sleep(step.seconds)
                else:
                    result = await _run_async(step, client)
            except Exception as error:
                step = plan.throw(error)
            else:
                step = plan.send(result)
    except StopIteration as finished:
        return finished.value


def _api_method(plan_function):
    """
    Turns a method that was written as a plan into a normal method that runs
    the plan when it's called. The plan is kept as method._plan.
    """
    @functools.wraps(plan_function)
    def method(*args, **kwargs):
        return _run(plan_function(*args, **kwargs))

    method._plan = plan_function

    return method


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
    Builds a request to the Salesforce REST API for the current API_VERSION.
    An API method sends it with: response = yield _rest_request(...)

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
        _Request: Returns the request to send.
    """
    header_details = Util.get_standard_header(access_token)

    if headers != None:
        header_details.update(headers)

    url = instance_url + '/services/data/v' + pysalesforceutils.API_VERSION + path

    return _Request(requestType=method, URL=url, data_body=_encode_body(data), header_details=header_details)


def _rest_json(method, path, access_token, instance_url, data=None, headers=None):
    """
    Does the same as _rest_request, but the result is the parsed JSON response
    body. An API method uses it with: json_response = yield _rest_json(...)
    """
    response = yield _rest_request(method, path, access_token, instance_url, data, headers)

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
    def soql_quote(value):
        """
        Turns a string into a quoted SOQL or SOSL string literal, escaping the
        characters that would otherwise end the string early. Use this for any
        value in a query that comes from a user or another system, e.g.:
            query = 'SELECT Id FROM Account WHERE Name = ' + Util.soql_quote(name)

        This doesn't escape the LIKE wildcards % and _.

        Args:
            value (str): The string value to use in the query

        Returns:
            str: Returns the value wrapped in single quotes with the special
                 characters escaped.
        """
        if not isinstance(value, str):
            raise TypeError('Only strings can be quoted for SOQL, not {}'.format(type(value).__name__))

        escaped_value = value.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n') \
            .replace('\r', '\\r').replace('\t', '\\t')

        return "'" + escaped_value + "'"

    @staticmethod
    def get_soap_client(wsdl_file):
        """
        Pass the wsdl and generate the soap client for the given WSDL

        Args:
            wsdl_file (str): The file location for the WSDL used to generate
                             the client

        Returns:
            Client: Returns the SOAP client. The same client is returned
                    each time this is called with the same wsdl_file.
        """
        if Client is None:
            raise ImportError(
                "The 'zeep' library is required to use the Metadata or SOAP APIs. "
                "Install it using `pip install zeep` or `pip install pysalesforceutils[soap]`."
            )

        # parsing a WSDL is slow, so each WSDL file is only loaded once
        if wsdl_file not in _soap_clients:
            _soap_clients[wsdl_file] = Client(_load_wsdl(wsdl_file))

        return _soap_clients[wsdl_file]

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
