#!/usr/bin/python3

"""
This package creates methods to easily call the various Salseforce APIs.
"""

import json
import webservice
import urllib
import time
import sys
import os
from mimetypes import MimeTypes
from zeep import Client, xsd, ns

API_VERSION = '50.0'
METADATA_WSDL_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'WSDL', 'metadata.wsdl')
METADATA_SANDBOX_WSDL_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'WSDL', 'metadata_sandbox.wsdl')

METADATA_SERVICE_BINDING = '{http://soap.sforce.com/2006/04/metadata}MetadataBinding'
PARTNER_WSDL_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'WSDL', 'partner.wsdl')
PARTNER_SANDBOX_WSDL_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'WSDL', 'partner_sandbox.wsdl')


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


class Authentication:
    """
    The Authentication class is used to log in and out of Salesforce
    """

    @staticmethod
    def get_oauth_login(login_username, login_password, login_client_id, login_client_secret, is_production):
        """
        this function logs into Salesforce using the oAuth 2.0 password grant type,
        and returns the response that can be used for other salesforce api requests.
        There are two parts of the response that will be needed, the token, and
        the instance url. The token can be retrieved with json_response['access_token'],
        and the instance url with json_response['instance_url']. In order for this
        function to work, a connected app must be set up in Salesforce, which is
        where the client id and client secret come from the Client Id is the
        connected app Consumer Key, and the client secret is the consumer secret.

        Args:
            login_username (str): this is the salesforce login
            login_password (str): this is the salesforce password AND security
                                  token
            login_client_id (str): this is the client Id from the oAuth settings
                                   in the Salesforce app setup
            login_client_secret (str): this is the secret from the oAuth settings
                                       in the Salesforce app setup
            is_production (bool): this is a boolean value to set whether or not
                                  the base oAuth connection will be in production
                                  or a sandbox environment
        Returns:
            object: returns the json from the login response body the important
                    aspects of the response are the access_token, which will be
                    used to authenticate the other calls, and instance_url,
                    which is the base endpoint used for the other calls
        """
        if is_production:
            base_oauth_url = 'https://login.salesforce.com/services/oauth2/token'
        else:
            base_oauth_url = 'https://test.salesforce.com/services/oauth2/token'

        login_body_data = {'grant_type': 'password', 'client_id': login_client_id, 'client_secret': login_client_secret,
                           'username': login_username, 'password': login_password}

        response = webservice.Tools.post_http_response(base_oauth_url, login_body_data, '')

        try:
            json_response = json.loads(response.text)
        except:
            json_response = response.text

        return json_response

    @staticmethod
    def get_oauth_logout(auth_token, is_production):
        """
        this function calls the correct endpoint for the oauth logout by providing
        the token and whether or not the login is production or test.

        Args:
            auth_token (str): this is the token received in the access_token
                              response from the get_oauth_login function.
            is_production (bool): this is a boolean value to set whether or not
                                  the base oAuth connection will be in production
                                  or a sandbox environment.
        Returns:
            object: returns a json response with success (True or False), and
                    the status_code returned by the call to revoke the token
        """
        if is_production:
            logout_url = 'https://login.salesforce.com/services/oauth2/revoke'
        else:
            logout_url = 'https://test.salesforce.com/services/oauth2/revoke'

        logout_body_data = {'host': logout_url, 'Content-Type': 'application/x-www-form-urlencoded',
                            'token': auth_token}

        response = webservice.Tools.post_http_response(logout_url, logout_body_data, '')

        success = False
        if response.status_code == 200:
            success = True

        json_response = {'success': success, 'status_code': response.status_code}

        return json_response

    @staticmethod
    def get_login_scope_header(org_id, portal_id):
        """
        Only use this for authenticating as a self-service user

        Args:
            org_id (str): The ID of the organization against which you will
                          authenticate Self-Service users.
            portal_id (str): Specify only if user is a Customer Portal user. The
                             ID of the portal for this organization.

        Returns:
            object: Returns the ScopeHeader for SOAP login requests.
        """
        login_scope_header = {}
        login_scope_header['organizationId'] = org_id

        if portal_id != None:
            login_scope_header['portalId'] = portal_id

        return login_scope_header

    @staticmethod
    def get_login_call_options(client_name, default_ns):
        """
        This creates the call options for the SOAP login.

        Args:
            client_name (str): A string that identifies a client.
            default_ns (str): A string that identifies a developer namespace
                              prefix. Use this field to resolve field names in
                              managed packages without having to fully specify
                              the fieldName everywhere.

        Returns:
            object: Returns the CallOptions for SOAP login requests.

        """
        call_options = {}

        if client_name != None:
            call_options['client'] = client_name

        if default_ns != None:
            call_options['defaultNamespace'] = default_ns

        return call_options

    @staticmethod
    def get_soap_headers(org_id, portal_id, client_name, default_ns):
        """
        This method builds the headers for soap calls. Leave org_id and
        portal_id as None if you are using a normal authentication. These
        values are only used for self-service authentication

        Args:
        org_id (str): The ID of the organization against which you will
                      authenticate Self-Service users.
        portal_id (str): Specify only if user is a Customer Portal user. The ID
                        of the portal for this organization.
        client_name (str): A string that identifies a client.
        default_ns (str): A string that identifies a developer namespace prefix.
                          Use this field to resolve field names in managed
                          packages without having to fully specify the fieldName
                          everywhere.
        Returns:
            object: Returns the SOAP headers needed to log in
        """
        client = Util.get_soap_client(PARTNER_WSDL_FILE)
        soap_headers = {}

        if org_id != None or portal_id != None:
            login_scope = Authentication.get_login_scope_header(org_id, portal_id)
            soap_headers['LoginScopeHeader'] = login_scope

        if client_name != None or default_ns != None:
            call_options = Authentication.get_login_call_options(client_name, default_ns)
            soap_headers['CallOptions'] = call_options

        return soap_headers

    @staticmethod
    def get_soap_login(login_username, login_password, org_id, portal_id, client_name, default_ns, is_production):
        """
        This method logs into Salesforce with SOAP given the provided details.
        Only use org_id and portal_id for self-service user authentication. For
        most purposes, these should be set to None. The client_name is actually a
        clientId used for partner applications and the default_ns is the default
        namespace used for an application. So these values can also be set to
        None for most requests. For most requests, you will only need the
        username and password.

        Args:
            login_username (str): this is the salesforce login
            login_password (str): this is the salesforce password AND security
                                  token
            org_id (str): The ID of the organization against which you will
                          authenticate Self-Service users.
            portal_id (str): Specify only if user is a Customer Portal user. The
                             ID of the portal for this organization.
            client_name (str): A string that identifies a client. Used for
                               partner applications.
            default_ns (str): A string that identifies a developer namespace
                              prefix. Use this field to resolve field names in
                              managed packages without having to fully specify
                              the fieldName everywhere.
            is_production (bool): this is a boolean value to set whether or not
                                  the base oAuth connection will be in
                                  production or a sandbox environment.
        Returns:
            object: returns a long response object that contains the session id
                    login_result['sessionId'], metadata server url
                    login_result['metadataServerUrl'] and server url
                    login_result['serverUrl']
        """
        wsdl_file = PARTNER_WSDL_FILE

        if not (is_production):
            wsdl_file = PARTNER_SANDBOX_WSDL_FILE

        client = Util.get_soap_client(wsdl_file)
        soap_headers = Authentication.get_soap_headers(org_id, portal_id, client_name, default_ns)
        login_result = client.service.login(login_username, login_password, _soapheaders=soap_headers)

        return login_result


class Tooling:
    """
    The purpose of this class is to expose the Salesforce Tooling API methods
    """
    base_tooling_uri = '/services/data/v' + API_VERSION + '/tooling'

    @staticmethod
    def completions(completions_type, access_token, instance_url):
        """
        Retrieves available code completions of the referenced type for Apex
        system method symbols (type=apex).

        Args:
        completions_type (str): The type of metadata to get completions for.
                                e.g. 'apex'
        access_token (str): This is the access_token value received from the
                            login response
        instance_url (str): This is the instance_url value received from the
                            login response

        Returns:
            object: Returns the completion values for the specified type
        """
        completions_uri = '/completions?type='
        header_details = Util.get_standard_header(access_token)
        url_encoded_type = urllib.parse.quote(completions_type)

        response = webservice.Tools.get_http_response(
            instance_url + Tooling.base_tooling_uri + completions_uri + url_encoded_type, header_details)
        json_response = json.loads(response.text)

        return json_response

    @staticmethod
    def execute_anonymous(code_string, access_token, instance_url):
        """
        This function executes anonymous apex, and returns a json response
        object. The response should contain a success value (True or False),
        column and line numbers, which return -1 if there are no issues,
        exceptionStackTrace which should be None if there are no problems,
        compiled (True or False), compileProblem which should be None if there
        are no problems, and exceptionMessage if an exception was thrown.

        Args:
            code_string (str): this is the non url encoded code string that you
                               would like to execute
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            object: returns the response result from executing the SFDC script
        """
        execute_anonymous_uri = '/executeAnonymous/?anonymousBody='
        header_details = Util.get_standard_header(access_token)
        url_encoded_code = urllib.parse.quote(code_string)

        response = webservice.Tools.get_http_response(
            instance_url + Tooling.base_tooling_uri + execute_anonymous_uri + url_encoded_code, header_details)
        json_response = json.loads(response.text)

        return json_response

    @staticmethod
    def query(query_string, access_token, instance_url):
        """
        Executes a query against an object and returns data that matches the
        specified criteria. Tooling API exposes objects like EntityDefinition and
        FieldDefinition that use the external object framework--that is, they don’t
        exist in the database but are constructed dynamically. Special query rules
        apply to virtual entities. If the query result is too large, it’s broken up
        into batches. The response contains the first batch of results and a query
        identifier. The identifier can be used in a request to retrieve the next
        batch. A list of the tooling api objects can be found here:
        https://developer.salesforce.com/docs/atlas.en-us.api_tooling.meta/api_tooling/reference_objects_list.htm

        Args:
            query_string (str): the query to be executed
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            object: returns a JSON object with the results of the query.
        """
        query_uri = '/query/?q='
        header_details = Util.get_standard_header(access_token)
        url_encoded_query = urllib.parse.quote(query_string)

        response = webservice.Tools.get_http_response(
            instance_url + Tooling.base_tooling_uri + query_uri + url_encoded_query, header_details)
        json_response = json.loads(response.text)

        return json_response

    @staticmethod
    def run_tests_asynchronous_list(class_ids, suite_ids, max_failed_tests, test_level, access_token, instance_url):
        """
        This method runs the tests provided with the class Ids or suite Ids, then
        returns the direct results from the Salesforce tooling API.

        Args:
            class_ids (array): List of comma separated class Ids to run the tests
            suite_ids (array): List of suite ids to run
            max_failed_tests (int): To stop the test run from executing new tests
                                    after a given number of tests fail, set to
                                    an integer value from 0 to 1,000,000. To
                                    allow all tests in your run to execute,
                                    regardless of how many tests fail, omit
                                    max_failed_tests or set it to -1
            test_level (str): The testLevel parameter is optional. If you don’t
                              provide a testLevel value, we use RunSpecifiedTests.
                              values:
                              RunSpecifiedTests - Only the tests that you
                                                  specify are run.
                              RunLocalTests - All tests in your org are run,
                                              except the ones that originate
                                              from installed managed packages.
                                              Omit identifiers for specific tests
                                              when you use this value.
                              RunAllTestsInOrg - All tests are run. The tests
                                                 include all tests in your org,
                                                 including tests of managed
                                                 packages. Omit identifiers for
                                                 specific tests when you use
                                                 this value.
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            object: returns the Id of the test run
        """
        test_async_uri = '/runTestsAsynchronous/'
        header_details = Util.get_standard_header(access_token)

        data_body = {}

        if class_ids != None:
            data_body['classids'] = class_ids

        if suite_ids != None:
            data_body['suiteids'] = suite_ids

        if max_failed_tests != None:
            data_body['maxFailedTests'] = max_failed_tests

        if test_level != None:
            data_body['testLevel'] = test_level

        json_data_body = json.dumps(data_body, indent=4, separators=(',', ': '))

        response = webservice.Tools.post_http_response(instance_url + Tooling.base_tooling_uri + test_async_uri,
                                                       json_data_body, header_details)
        json_response = json.loads(response.text)

        return json_response

    @staticmethod
    def run_tests_asynchronous_json(test_array, access_token, instance_url):
        """
        This method runs specified tests in the test_array with more control than
        the run_tests_asynchronous_list method by allowing you to specify which methods
        you'd like to run with each test class.

        Args:
        test_array (array): This is an array of tests that you'd like to run with
                            the specified methods if you wish. Like the
                            run_tests_asynchronous_list method, you can also specify
                            the maxFailedTests and testLevel values
                            e.g.
                                [
                                {"classId": "01pD0000000Fhy9IAC",
                                    "testMethods": ["testMethod1","testMethod2", "testMethod3"]},
                                {"classId": "01pD0000000FhyEIAS",
                                    "testMethods": ["testMethod1","testMethod2", "testMethod3"]},
                                {"maxFailedTests": "2"},
                                {"testLevel": "RunSpecifiedTests"}
                                ]
        access_token (str): This is the access_token value received from the
                            login response
        instance_url (str): This is the instance_url value received from the
                            login response

        Returns:
            object: returns the Id of the test run
        """
        test_async_uri = '/runTestsAsynchronous/'
        header_details = Util.get_standard_header(access_token)
        data_body = {'tests': test_array}
        json_data_body = json.dumps(data_body, indent=4, separators=(',', ': '))

        response = webservice.Tools.post_http_response(instance_url + Tooling.base_tooling_uri + test_async_uri,
                                                       json_data_body, header_details)
        json_response = json.loads(response.text)

        return json_response


class Standard:
    """
    This class provides a front end for the Salesforce standard REST API. More
    details about this can be found here:
    https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/intro_what_is_rest_api.htm
    You can get more details about each of the methods by looking in the reference
    section of the documentation.
    """
    base_standard_uri = '/services/data/'

    @staticmethod
    def versions(access_token, instance_url):
        """
        Lists summary information about each Salesforce version currently available,
        including the version, label, and a link to each version's root.

        Args:
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            object: Returns an object with the list of Salesforce versions
        """
        header_details = Util.get_standard_header(access_token)

        response = webservice.Tools.get_http_response(instance_url + Standard.base_standard_uri, header_details)
        json_response = json.loads(response.text)

        return json_response

    @staticmethod
    def resources_by_version(version_num_string, access_token, instance_url):
        """
        This method returns the available resources (API services) available for
        the supplied version number.

        Args:
            version_num_string (str): This is the version number as a string,
                                      e.g. 37.0
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            object: Returns an object containing the list of available resources
                    for this version number.
        """
        header_details = Util.get_standard_header(access_token)

        response = webservice.Tools.get_http_response(
            instance_url + Standard.base_standard_uri + 'v' + version_num_string + '/', header_details)
        json_response = json.loads(response.text)

        return json_response

    @staticmethod
    def get_sobject_row(object_name, record_id, field_list_string, access_token, instance_url):
        """
        Provides the details requested for the specified record. In practice, if you
        provide an explicit list of fields, it will be just like a query for that
        record, but if you leave the fields blank, this will return a lot if not
        all fields. I'm not sure about that because the description of what is
        returned if you leave the fields empty isn't explained in the API documentation

        Args:
            object_name (str): The API name of the object.
            record_id (str): The record Id you're trying to retrieve
            field_list_string (str): List of comma separated values for fields
                                     to retrieve
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            dict: returns the record with the explicit field list, or all (or
                a lot) of the fields if the field_list_string is None.
        """
        get_row_uri = '/sobjects/' + object_name + '/' + record_id
        header_details = Util.get_standard_header(access_token)

        if field_list_string != None:
            get_row_uri = get_row_uri + '?fields=' + field_list_string

        response = webservice.Tools.get_http_response(
            instance_url + Standard.base_standard_uri + 'v' + API_VERSION + get_row_uri, header_details)
        json_response = json.loads(response.text)

        return json_response

    @staticmethod
    def get_sobject_blob(object_name, record_id, access_token, instance_url):
        """
        Provides the details requested for the specified record blob field. This will retrieve the
        BLOB field for Attachments/ContentVersion/Document.  Example call:
            response = Standard.get_sobject_blob('Attachment', 'attachmentId', access_token, instance_url)
            with open('test.jpg', 'wb') as new_file:
                for chunk in response.iter_content(chunk_size=1024):
                    new_file.write(chunk)

        Args:
            object_name (str): The API name of the object.
            record_id (str): The record Id of the Attachment you're trying to retrieve
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            object: returns the record with the explicit field list, or all (or
                    a lot) of the fields if the field_list_string is None.
        """
        object_to_blob_map = {
            "Attachment": "Body",
            "ContentVersion": "VersionData",
            "Document": "Body"
        }

        get_row_uri = '/sobjects/' + object_name + '/' + record_id + '/' + object_to_blob_map[object_name]
        header_details = Util.get_standard_header(access_token)

        response = webservice.Tools.get_http_response(
            instance_url + Standard.base_standard_uri + 'v' + API_VERSION + get_row_uri, header_details)

        return response

    @staticmethod
    def create_sobject_blob_record(object_name, record_json, file, access_token, instance_url):
        """
        Creates the provided record in the recordJson param and binary multipart message

        Args:
            object_name (str): The API name of the object.
            record_json (object): The JSON describing the fields you want to
                                  update on the given object. You should pass in
                                  a python object and it will be converted to a
                                  json string to send the request. This object
                                  is just the key value paris for the record
                                  update. e.g.:
                                      {
                                          'BillingCity': 'Bellevue',
                                          'BillingState': 'WA'
                                      }
            file (str): file object
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response
        Returns:
            object: returns the text from the creation response
        """
        post_row_uri = '/sobjects/'+ object_name + '/'
        header_details = {"Authorization": "Bearer " + access_token}
        mimetype = MimeTypes().guess_type(os.path.basename(file.name))[0] or 'application/octet-stream'

        object_to_blob_map = {
            "Attachment": {"BlobField": "Body",
                           "FileNameField": "Name",
                           "ParentField": "ParentId"
                           },
            "ContentVersion": {"BlobField": "VersionData",
                               "FileNameField": "PathOnClient",
                               "ParentField": "FirstPublishLocationId"
                               },
            "Document": {"BlobField": "Body",
                         "FileNameField": "Name",
                         "ParentField": "ParentId"
                         },
        }

        object_fields = object_to_blob_map[object_name]

        multipart_files = {
            'entity_'+object_name: (None, json.dumps(record_json), 'application/json'),
            object_fields['BlobField']: (record_json[object_fields['FileNameField']], file, mimetype)
        }

        response = webservice.Tools.post_http_response(
            instance_url + Standard.base_standard_uri + 'v' + API_VERSION + post_row_uri, None,
            header_details, multipart_files)
        response_text = ""

        if response.status_code is 204:
            response_text = "Update Successful"
        else:
            response_text = response.text

        return response_text

    @staticmethod
    def create_sobject_row(object_name, record_json, run_assignment_rules, access_token, instance_url):
        """
        Creates the provided record in the recordJson param

        Args:
            object_name (str): The API name of the object.
            record_json (dict): The JSON describing the fields you want to
                                update on the given object. You should pass in
                                a python object and it will be converted to a
                                json string to send the request. This object
                                is just the key value paris for the record
                                update. e.g.:
                                    {
                                        'BillingCity': 'Bellevue',
                                        'BillingState': 'WA'
                                    }
            instance_url (str): This is the instance_url value received from the
                                login response
        Returns:
            dict: returns the text from the creation response
        """
        post_row_uri = '/sobjects/' + object_name + '/'
        header_details = Util.get_standard_header(access_token)

        if run_assignment_rules:
            header_details["Sforce-Auto-Assign"] = "true"
        else:
            header_details["Sforce-Auto-Assign"] = "false"

        data_body_json = json.dumps(record_json, indent=4, separators=(',', ': '))

        response = webservice.Tools.post_http_response(
            instance_url + Standard.base_standard_uri + 'v' + API_VERSION + post_row_uri, data_body_json,
            header_details)
        response_text = ""

        if response.status_code is 204:
            response_text = "Update Successful"
        else:
            response_text = response.text

        return response_text

    @staticmethod
    def get_sobject_rows(object_name, record_id_list_string, field_list_string, access_token, instance_url):
        """
        Provides the details requested for the specified record id list. In practice, if you
        provide an explicit list of fields, it will be just like a query for that
        record, but if you leave the fields blank, this will return a lot if not
        all fields. I'm not sure about that because the description of what is
        returned if you leave the fields empty isn't explained in the API documentation

        Args:
            object_name (str): The API name of the object.
            record_id_list_string (str): The record id list you're trying to retrieve
            field_list_string (str): List of comma separated values for fields
                                     to retrieve
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            dict: returns the record with the explicit field list, or all (or
                a lot) of the fields if the field_list_string is None.
        """

        get_row_uri = '/composite/sobjects/' + object_name
        header_details = Util.get_standard_header(access_token)

        get_rows_uri = get_row_uri + '?ids=' + record_id_list_string + '&fields=' + field_list_string

        response = webservice.Tools.get_http_response(
            instance_url + Standard.base_standard_uri + 'v' + API_VERSION + get_rows_uri, header_details)
        json_response = json.loads(response.text)

        return json_response

    @staticmethod
    def create_sobject_rows(records, all_or_none, run_assignment_rules, access_token, instance_url):
        """
        Creates a list of up to 200 records.
        documentation: https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_composite_sobjects_collections.htm

        Args:
            records_json (object): The JSON describing the records you want to
                                   insert on the given object. Each object needs
                                   to contain an attributes field that contains
                                   the "type" which is the object name.
                                   example:
                                       [{
                                          "attributes" : {"type" : "Account"},
                                          "Name" : "example.com",
                                          "BillingCity" : "San Francisco"
                                       }, {
                                          "attributes" : {"type" : "Contact"},
                                          "LastName" : "Johnson",
                                          "FirstName" : "Erica"
                                       }]
            all_or_none (bool): Indicates whether to roll back the entire request
                                when the update of any object fails (true) or to
                                continue with the independent update of other
                                objects in the request. The default is false.
            run_assignment_rules (bool): If true this will add the assginment
                                         rule header to the request.
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            dict: Returns a response object that should have a success or failure
                 for each item in the request in the same order.
                 example:
                [
                   {
                      "success" : false,
                      "errors" : [
                         {
                            "statusCode" : "DUPLICATES_DETECTED",
                            "message" : "Use one of these records?",
                            "fields" : [ ]
                         }
                      ]
                   },
                   {
                      "success" : false,
                      "errors" : [
                         {
                            "statusCode" : "ALL_OR_NONE_OPERATION_ROLLED_BACK",
                            "message" : "Record rolled back because not all records were valid and the request was using AllOrNone header",
                            "fields" : [ ]
                         }
                      ]
                   }
                ]
        """
        post_rows_uri = '/composite/sobjects'
        header_details = Util.get_standard_header(access_token)

        if run_assignment_rules:
            header_details["Sforce-Auto-Assign"] = "true"
        else:
            header_details["Sforce-Auto-Assign"] = "false"

        request_body = {}
        request_body["allOrNone"] = all_or_none
        request_body["records"] = records

        data_body_json = json.dumps(request_body, indent=4, separators=(',', ': '))

        response = webservice.Tools.post_http_response(
            instance_url + Standard.base_standard_uri + 'v' + API_VERSION + post_rows_uri, data_body_json,
            header_details)

        return json.loads(response.text)

    @staticmethod
    def update_sobject_row(object_name, record_id, record_json, run_assignment_rules, access_token, instance_url):
        """
        Updates a specific record with the data in the record_json param

        Args:
            object_name (str): The API name of the object.
            record_id (str): The record Id you're trying to update

            record_json (dict): The JSON describing the fields you want to
                                  update on the given object. You should pass in
                                  a python object and it will be converted to a
                                  json string to send the request. This object
                                  is just the key value paris for the record
                                  update. e.g.:
                                      {
                                          'BillingCity': 'Bellevue',
                                          'BillingState': 'WA'
                                      }
            run_assignment_rules (bool): If true this will add the assginment
                                         rule header to the request.
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            str: This only returns 'Update Successful' if the update worked, or
                 returns an error message if the update wasn't successful. The
                 response isn't more detailed because Salesforce returns no
                 text, only a response code of 204
        """
        patch_row_uri = '/sobjects/' + object_name + '/' + record_id
        header_details = Util.get_standard_header(access_token)
        header_details["Sforce-Auto-Assign"] = "true" if run_assignment_rules else "false"

        data_body_json = json.dumps(record_json, indent=4, separators=(',', ': '))

        response = webservice.Tools.patch_http_response(
            instance_url + Standard.base_standard_uri + 'v' + API_VERSION + patch_row_uri, data_body_json,
            header_details)
        response_text = ""

        if response.status_code is 204:
            response_text = "Update Successful"
        else:
            response_text = response.text

        return response_text

    @staticmethod
    def update_sobject_rows(records, all_or_none, run_assignment_rules, access_token, instance_url):
        """
        Updates a list of up to 200 records.
        documentation: https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_composite_sobjects_collections.htm

        Args:
            records_json (object): The JSON describing the records you want to
                                   insert on the given object. Each object needs
                                   to contain an attributes field that contains
                                   the "type" which is the object name, and an
                                   "id" field which is the record id for
                                   each record being updated. This key is used
                                   in the response to show a result for each
                                   record being updated.
                                   example:
                                       [{
                                          "attributes" : {"type" : "Account"},
                                          "id" : "001xx000003DGb2AAG",
                                          "Name" : "example.com",
                                          "BillingCity" : "San Francisco"
                                       }, {
                                          "attributes" : {"type" : "Contact"},
                                          "id": "003xx000004TmiQAAS",
                                          "LastName" : "Johnson",
                                          "FirstName" : "Erica"
                                       }]
            all_or_none (bool): Indicates whether to roll back the entire request
                                when the update of any object fails (true) or to
                                continue with the independent update of other
                                objects in the request. The default is false.
            run_assignment_rules (bool): If true this will add the assginment
                                         rule header to the request.
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            dict: Returns a response object that should have a success or failure
                  for each item in the request in the same order.
                example:
                [
                   {
                      "id" : "001xx000003DGb2AAG",
                      "success" : true,
                      "errors" : [ ]
                   },
                   {
                      "id" : "003xx000004TmiQAAS",
                      "success" : true,
                      "errors" : [ ]
                   }
                ]
        """
        patch_rows_uri = '/composite/sobjects'
        header_details = Util.get_standard_header(access_token)

        if run_assignment_rules:
            header_details["Sforce-Auto-Assign"] = "true"
        else:
            header_details["Sforce-Auto-Assign"] = "false"

        request_body = {}
        request_body["allOrNone"] = all_or_none
        request_body["records"] = records

        data_body_json = json.dumps(request_body, indent=4, separators=(',', ': '))

        response = webservice.Tools.patch_http_response(
            instance_url + Standard.base_standard_uri + 'v' + API_VERSION + patch_rows_uri, data_body_json,
            header_details)

        return json.loads(response.text)

    @staticmethod
    def upsert_sobject_rows(object_api_name, records, access_token, instance_url, all_or_none=False, run_assignment_rules=False, external_id_field_name='Id'):
        """
        Upserts a list of up to 200 records.
        documentation: https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_composite_sobjects_collections_upsert.htm

        Args:
            object_api_name (str): The API Name of the object being updated
            records (object): The JSON describing the records you want to
                              insert on the given object. Each object needs
                              to contain an attributes field that contains
                              the "type" which is the object name, and an
                              "id" field which is the record id for
                              each record being updated. This key is used
                              in the response to show a result for each
                              record being updated.
                              example:
                                       [{
                                          "attributes" : {"type" : "Account", "id" : "001xx000003DGb2AAG"},
                                          "Name" : "example.com",
                                          "BillingCity" : "San Francisco"
                                       }, {
                                          "attributes" : {"type" : "Contact", "id": "003xx000004TmiQAAS"},
                                          "LastName" : "Johnson",
                                          "FirstName" : "Erica"
                                       }]
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response
            all_or_none (bool): Indicates whether to roll back the entire request
                                when the update of any object fails (true) or to
                                continue with the independent update of other
                                objects in the request. The default is false.
            run_assignment_rules (bool): If true this will add the assginment
                                         rule header to the request.
            external_id_field_name (str): This is the external Id field that is
                                          used to determine whether this record
                                          will be inserted or updated. This is
                                          required for upserts, but will default
                                          to the record Id field

        Returns:
            list: A list of the response from each of the upsert requests in the
                  request list.
                  [
                      {
                          "id": "001xx0000004GxDAAU",
                          "success": true,
                          "errors": [],
                          "created": true
                      },
                      {
                          "id": "001xx0000004GxEAAU",
                          "success": true,
                          "errors": [],
                          "created": false
                      }
                  ]
        """
        # /composite/sobjects/SobjectName/ExternalIdFieldName
        patch_rows_uri = "/composite/sobjects/" + object_api_name + "/" + external_id_field_name
        header_details = Util.get_standard_header(access_token)

        if run_assignment_rules:
            header_details["Sforce-Auto-Assign"] = "true"
        else:
            header_details["Sforce-Auto-Assign"] = "false"

        request_body = {}
        request_body["allOrNone"] = all_or_none
        request_body["records"] = records

        data_body_json = json.dumps(request_body, indent=4, separators=(',', ': '))

        response = webservice.Tools.patch_http_response(
            instance_url + Standard.base_standard_uri + 'v' + API_VERSION + patch_rows_uri, data_body_json,
            header_details)

        return json.loads(response.text)

    @staticmethod
    def delete_sobject_rows(record_ids, all_or_none, access_token, instance_url):
        """
        Deletes a list of up to 200 records.
        documentation: https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_composite_sobjects_collections.htm

        Args:
            record_ids (list): List of record Ids to be deleted.
            all_or_none (bool): Indicates whether to roll back the entire request
                                when the update of any object fails (true) or to
                                continue with the independent update of other
                                objects in the request. The default is false.
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            dict: The result in order of the Id delete list requested.
                example:
                [
                   {
                      "id" : "001RM000003oLruYAE",
                      "success" : false,
                      "errors" : [
                         {
                            "statusCode" : "ALL_OR_NONE_OPERATION_ROLLED_BACK",
                            "message" : "Record rolled back because not all records were valid and the request was using AllOrNone header",
                            "fields" : [ ]
                         }
                      ]
                   },
                   {
                      "success" : false,
                      "errors" : [
                         {
                            "statusCode" : "MALFORMED_ID",
                            "message" : "malformed id 001RM000003oLrB000",
                            "fields" : [ ]
                         }
                      ]
                   }
                ]
        """
        delete_rows_uri = '/composite/sobjects'
        header_details = Util.get_standard_header(access_token)

        delete_params = "?ids=" + ",".join(record_ids)

        if all_or_none:
            delete_params += "&allOrNone=true"
        else:
            delete_params += "&allOrNone=false"

        response = webservice.Tools.delete_http_response(
            instance_url + Standard.base_standard_uri + 'v' + API_VERSION + delete_rows_uri + delete_params, None,
            header_details)

        return json.loads(response.text)

    @staticmethod
    def query(query_string, access_token, instance_url):
        """
        Executes the specified SOQL query. If the query results are too large,
        the response contains the first batch of results and a query identifier
        in the nextRecordsUrl field of the response. The identifier can be used
        in an additional request to retrieve the next batch.

        Args:
            query_string (str): This query you'd like to run
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            object: returns the query results, if they are too large, then it
                    will also return a nextRecordsUrl to get more records.
        """
        query_uri = '/query/?q='
        header_details = Util.get_standard_header(access_token)
        url_encoded_query = urllib.parse.quote(query_string)

        response = webservice.Tools.get_http_response(
            instance_url + Standard.base_standard_uri + 'v' + API_VERSION + query_uri + url_encoded_query,
            header_details)
        json_response = json.loads(response.text)

        return json_response

    @staticmethod
    def query_all(query_string, access_token, instance_url):
        """
        Executes the specified SOQL query. If the query results are too large,
        the response contains the first batch of results and a query identifier
        in the nextRecordsUrl field of the response. The identifier can be used
        in an additional request to retrieve the next batch. The difference
        between this and query is that query all can retrieve deleted records.

        Args:
            query_string (str): This query you'd like to run
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            object: returns the query results, if they are too large, then it
                    will also return a nextRecordsUrl to get more records.
        """
        query_uri = '/queryAll/?q='
        header_details = Util.get_standard_header(access_token)
        url_encoded_query = urllib.parse.quote(query_string)

        response = webservice.Tools.get_http_response(
            instance_url + Standard.base_standard_uri + 'v' + API_VERSION + query_uri + url_encoded_query,
            header_details)
        json_response = json.loads(response.text)

        return json_response

    @staticmethod
    def reset_users_password(user_id, access_token, instance_url):
        """
        Resets a users' password.

        Args:
            user_id (str):      The user id of the user who's password should be reset
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            object: returns information about the password reset
        """
        query_uri = f'/sobjects/User/{user_id}/password'
        header_details = Util.get_standard_header(access_token)

        response = webservice.Tools.delete_http_response(
            instance_url + Standard.base_standard_uri + 'v' + API_VERSION + query_uri, None,
            header_details)
        json_response = json.loads(response.text)

        return json_response

    @staticmethod
    def get_current_user_info(access_token, instance_url):
        """
        Gets information about the currently logged in user.

        Args:
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            object: returns information about the current user
        """
        query_uri = '/chatter/users/me'
        header_details = Util.get_standard_header(access_token)

        response = webservice.Tools.get_http_response(
            instance_url + Standard.base_standard_uri + 'v' + API_VERSION + query_uri,
            header_details)
        json_response = json.loads(response.text)

        return json_response

    @staticmethod
    def post_chatter_mention(text, mention_id, subject_id, access_token, instance_url):
        """
        Posts a chatter mention. E.g. @someone

        Args:
            text (str): The text to go after the mention
            mention_id (str): The id of the user/group you want to mention
            subject_id (str): The id of the object you want to attach the comment to
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            object: returns the query results, if they are too large, then it
                    will also return a nextRecordsUrl to get more records.
        """
        query_uri = '/chatter/feed-elements'
        header_details = Util.get_standard_header(access_token)
        request_body = {}
        request_body['body'] = {}
        request_body['body']["messageSegments"] = [{"type": "Mention", "id": mention_id}, {'type': 'Text', "text": text}]
        request_body["feedElementType"] = "FeedItem"
        request_body["subjectId"] = subject_id

        data_body_json = json.dumps(request_body, indent=4, separators=(',', ': '))

        response = webservice.Tools.post_http_response(
            instance_url + Standard.base_standard_uri + 'v' + API_VERSION + query_uri, data_body_json,
            header_details)
        json_response = json.loads(response.text)

        return json_response

    @staticmethod
    def get_next_query_batch(next_record_url, access_token, instance_url):
        """
        Does a GET on the url passed. If the query results are still too large,
        the response contains the first batch of results and a query identifier
        in the nextRecordsUrl field of the response. The identifier can be used
        in an additional request to retrieve the next batch.

        Args:
            next_record_url (str): The url of the next record
            access_token (str)   : This is the access_token value received from the
                                   login response
            instance_url (str)   : This is the instance_url value received from the
                                   login response

        Returns:
            object: returns the query results, if they are too large, then it
                    will also return a nextRecordsUrl to get more records.
        """
        header_details = Util.get_standard_header(access_token)

        response = webservice.Tools.get_http_response(instance_url + next_record_url,
            header_details)

        json_response = json.loads(response.text)

        return json_response

    @staticmethod
    def get_updated(object_name, start_date_time, end_date_time, access_token, instance_url):
        """
        Retrieves the list of individual records that have been updated (added
        or changed) within the given timespan for the specified object. SObject
        Get Updated is available in API version 29.0 and later.

        This resource is commonly used in data replication applications. Note
        the following considerations:
            * Results are returned for no more than 30 days previous to the day
              the call is executed.
            * Your client application can replicate any objects to which it has
              sufficient permissions. For example, to replicate all data for
              your organization, your client application must be logged in with
              “View All Data” access rights to the specified object. Similarly,
              the objects must be within your sharing rules.
            * There is a limit of 600,000 IDs returned from this resource. If
              more than 600,000 IDs would be returned, EXCEEDED_ID_LIMIT is
              returned. You can correct the error by choosing start and end
              dates that are closer together.

        Args:
            object_name (str): The name of the object to get updated records for.

            startDateTime (datetime): Starting date/time (Coordinated Universal
                Time (UTC) time zone—not local— timezone) of the timespan for
                which to retrieve the data. The API ignores the seconds portion
                of the specified dateTime value (for example, 12:30:15 is
                interpreted as 12:30:00 UTC).

            start_date_time (datetime): Ending date/time (Coordinated Universal
                Time (UTC) time zone—not local— timezone) of the timespan for
                which to retrieve the data. The API ignores the seconds portion
                of the specified dateTime value (for example, 12:35:15 is
                interpreted as 12:35:00 UTC).

            access_token (str): This is the access_token value received from the
                                login response

            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            dict: Returns a dictionary containing the record Ids that were
                updated and the latest record updated in that window.
                {
                    'ids': ['<id 1>', ..., '<id N>'],
                    'latestDateCovered': '2020-03-13T12:00:00.000+0000'
                }
        """
        get_updated_uri = '/sobjects/' + object_name + '/updated/?start=' + \
            urllib.parse.quote(start_date_time.strftime('%Y-%m-%dT%H:%M:%SZ')) + '&end=' + \
            urllib.parse.quote(end_date_time.strftime('%Y-%m-%dT%H:%M:%SZ'))

        header_details = Util.get_standard_header(access_token)

        response = webservice.Tools.get_http_response(
            instance_url + Standard.base_standard_uri + 'v' + API_VERSION + get_updated_uri,
            header_details)
        json_response = json.loads(response.text)

        return json_response

    @staticmethod
    def retrieve(object_name, ids, fields, access_token, instance_url):
        """
        Use a GET or POST request with sObject Collections to retrieve one or
        more records of the same object type. A list of sObjects that represents
        the individual records of the specified type is returned. The number of
        sObjects returned matches the number of IDs passed in the request.

        You can specify approximately 800 IDs before the URL length causes the
        HTTP 414 error URI too long. To retrieve more records than the URL
        length can accommodate, use a POST request to retrieve up to 2,000
        records of the same object type. If you use POST, the IDs and fields of
        the records to retrieve are specified in the request body.

        Args:
            object_name (str): The name of the object to get updated records for.

            ids (list): A list of one or more IDs of the objects to return. All
                IDs must belong to the same object type.

            fields (list): A list of fields to include in the response. The
                field names you specify must be valid, and you must have
                read-level permissions to each field.

            access_token (str): This is the access_token value received from the
                login response

            instance_url (str): This is the instance_url value received from the
                login response

        Returns:
            list: A list of dicts with the Salesforce records: Example:
            [
                {
                    "attributes" : {
                        "type" : "Account",
                        "url" : "/services/data/v51.0/sobjects/Account/001xx000003DGb1AAG"
                    },
                    "Id" : "001xx000003DGb1AAG",
                    "Name" : "Acme"
                },
                {
                    "attributes" : {
                         "type" : "Account",
                        "url" : "/services/data/v51.0/sobjects/Account/001xx000003DGb0AAG"
                    },
                    "Id" : "001xx000003DGb0AAG",
                    "Name" : "Global Media"
                },
                None
            ]
        """
        retrieve_uri = '/composite/sobjects/' + object_name
        header_details = Util.get_standard_header(access_token)

        request_body = {}
        request_body['ids'] = ids
        request_body['fields'] = fields

        data_body_json = json.dumps(request_body, indent=4, separators=(',', ': '))

        response = webservice.Tools.post_http_response(
            instance_url + Standard.base_standard_uri + 'v' + API_VERSION + retrieve_uri, data_body_json,
            header_details)
        json_response = json.loads(response.text)

        return json_response

    @staticmethod
    def get_deleted(object_name, start_date_time, end_date_time, access_token, instance_url):
        """
        Retrieves the list of individual records that have been deleted within
        the given timespan for the specified object. SObject Get Deleted is
        available in API version 29.0 and later.

        This resource is commonly used in data replication applications. Note
        the following considerations:
            * Results are returned for no more than 30 days previous to the day
              the call is executed.
            * Your client application can replicate any objects to which it has
              sufficient permissions. For example, to replicate all data for
              your organization, your client application must be logged in with
              “View All Data” access rights to the specified object. Similarly,
              the objects must be within your sharing rules.
            * There is a limit of 600,000 IDs returned from this resource. If
              more than 600,000 IDs would be returned, EXCEEDED_ID_LIMIT is
              returned. You can correct the error by choosing start and end
              dates that are closer together.

        Args:
            object_name (str): The name of the object to get deleted records for.

            startDateTime (datetime): Starting date/time (Coordinated Universal
                Time (UTC) time zone—not local— timezone) of the timespan for
                which to retrieve the data. The API ignores the seconds portion
                of the specified dateTime value (for example, 12:30:15 is
                interpreted as 12:30:00 UTC).

            start_date_time (datetime): Ending date/time (Coordinated Universal
                Time (UTC) time zone—not local— timezone) of the timespan for
                which to retrieve the data. The API ignores the seconds portion
                of the specified dateTime value (for example, 12:35:15 is
                interpreted as 12:35:00 UTC).

            access_token (str): This is the access_token value received from the
                                login response

            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            dict: Returns a dictionary containing the record Ids that were
                deleted and the latest record deleted in that window.
                {
                    'ids': ['<id 1>', ..., '<id N>'],
                    'latestDateCovered': '2020-03-13T12:00:00.000+0000'
                }
        """
        get_deleted_uri = '/sobjects/' + object_name + '/deleted/?start=' + \
            urllib.parse.quote(start_date_time.strftime('%Y-%m-%dT%H:%M:%SZ')) + '&end=' + \
            urllib.parse.quote(end_date_time.strftime('%Y-%m-%dT%H:%M:%SZ'))

        header_details = Util.get_standard_header(access_token)

        response = webservice.Tools.get_http_response(
            instance_url + Standard.base_standard_uri + 'v' + API_VERSION + get_deleted_uri,
            header_details)
        json_response = json.loads(response.text)

        return json_response

    @staticmethod
    def graph_composite_request(request_body, access_token, instance_url):
        """
        https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_composite_graph_introduction.htm#!

        Composite graphs provide an enhanced way to perform composite requests,
        which execute a series of REST API requests in a single call.
          * Regular composite requests allow you to execute a series of REST API
            requests in a single call. And you can use the output of one request
            as the input to a subsequent request.
          * Composite graphs extend this by allowing you to assemble a more
            complicated and complete series of related objects and records.
          * Composite graphs also enable you to ensure that the steps in a given
            set of operations are either all completed or all not completed.
            This avoids requiring you to check for a mix of successful and
            unsuccessful results.
          * Regular composite requests have a limit of 25 subrequests. Composite
            graphs increase this limit to 500. This gives a single API call much
            greater power.

        Args:
            request_body (dict): The request body contains a list of graphs.
                Each graph must have a graphId, and a composite request. The
                composite requests are then built just like the original
                composite requests. An example request looks like this:
                {
                   "graphs": [{
                      "graphId": "graph1",
                      "compositeRequest": [{
                            "body": {
                               "name": "Cloudy Consulting"
                            },
                            "method": "POST",
                            "referenceId": "reference_id_account_1",
                            "url": "/services/data/v50.0/sobjects/Account/"
                         },
                         {
                            "body": {
                               "FirstName": "Nellie",
                               "LastName": "Cashman",
                               "AccountId": "@{reference_id_account_1.id}"
                            },
                            "method": "POST",
                            "referenceId": "reference_id_contact_1",
                            "url": "/services/data/v50.0/sobjects/Contact/"
                         }
                      ]
                   }]
                }

            access_token (str): This is the access_token value received from the
                                login response

            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            dict: The dict returns an object containing a list of the graphs and
                the results.
                {
                    "graphs": [
                        {
                            "graphId": "graph1",
                            "graphResponse": {
                                "compositeResponse": {
                                    <response from the composite request>
                                }
                            }
                        }
                    ]
                }

            output_records = salesforce_records["graphs"][0]["graphResponse"]["compositeResponse"]
        """
        graph_uri = '/composite/graph'

        header_details = Util.get_standard_header(access_token)

        data_body_json = json.dumps(request_body, indent=4, separators=(',', ': '))

        response = webservice.Tools.post_http_response(
            instance_url + Standard.base_standard_uri + 'v' + API_VERSION + graph_uri, data_body_json,
            header_details)
        json_response = json.loads(response.text)

        return json_response


    @staticmethod
    def get_object_describe(object_name, modified_since_date, access_token, instance_url):
        """
        Completely describes the individual metadata at all levels for the
        specified object. For example, this can be used to retrieve the fields,
        URLs, and child relationships for the Account object.

        The If-Modified-Since header param should be provided as GMT time if it
        is provided. If the object metadata has not changed since the provided
        date, a 304 Not Modified status code is returned, with no response body.

        Args:
            object_name (str): The name of the object to get the describe
                details for.

            modified_since_date (datetime): If None, this header will not be
                used. If provided, it will converted to appropriate format for
                the header and time should be in GMT.

            access_token (str): This is the access_token value received from the
                login response

            instance_url (str): This is the instance_url value received from the
                login response
        Returns:
            dict: Returns a dictionary with the metadata description of the
                given object.
        """
        describe_uri = "/sobjects/{}/describe/".format(object_name)

        header_details = Util.get_standard_header(access_token)

        if modified_since_date:
            modified_since_date = modified_since_date.strftime('%a, %-d %b %Y %H:%M:%S GMT')
            header_details["If-Modified-Since"] = modified_since_date

        response = webservice.Tools.get_http_response(
            instance_url + Standard.base_standard_uri + 'v' + API_VERSION + describe_uri,
            header_details)
        json_response = json.loads(response.text)

        return json_response


class Bulk:
    """
    This class is used for doing bulk operations. Please use this and not the
    Standard class singular methods when you're performing DML operations. This
    is faster and will use fewer of your API calls.
    API details here: https://developer.salesforce.com/docs/atlas.en-us.api_asynch.meta/api_asynch/asynch_api_intro.htm
    examples here: https://trailhead-salesforce-com.firelayers.net/en/api_basics/api_basics_bulk
    Considerations here: https://developer.salesforce.com/docs/atlas.en-us.salesforce_app_limits_cheatsheet.meta/salesforce_app_limits_cheatsheet/salesforce_app_limits_platform_bulkapi.htm
    """
    base_bulk_uri = '/services/async/' + API_VERSION
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
                instance_url + Bulk.base_bulk_uri + Bulk.batch_uri + '/' + job_id, header_details)
            json_response = json.loads(response.text)

            if verbose:
                print("Batches completed/failed/total: {}/{}/{}".format(json_response['numberBatchesCompleted'],
                                                                        json_response['numberBatchesFailed'],
                                                                        json_response['numberBatchesTotal']))

            total_jobs_run = json_response['numberBatchesCompleted'] + json_response['numberBatchesFailed']
            if total_jobs_run == json_response['numberBatchesTotal']:
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
            instance_url + Bulk.base_bulk_uri + Bulk.batch_uri + '/' + job_id + '/batch/' + batch_id + '/result',
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
            instance_url + Bulk.base_bulk_uri + Bulk.batch_uri + '/' + job_id + '/batch/' + batch_id + '/result' + '/' + query_result_id,
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
                instance_url + Bulk.base_bulk_uri + Bulk.batch_uri + '/' + job_id + '/batch', records_json,
                header_details)
            json_job_batch_response = json.loads(job_batch_response.text)
            batch_id = json_job_batch_response['id']
            batch_ids.append(batch_id)

        # close the bulk job
        close_body = {'state': 'Closed'}
        json_close_body = json.dumps(close_body, indent=4, separators=(',', ': '))
        close_response = webservice.Tools.post_http_response(
            instance_url + Bulk.base_bulk_uri + Bulk.batch_uri + '/' + job_id, json_close_body, header_details)
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
            instance_url + Bulk.base_bulk_uri + Bulk.batch_uri + '/' + job_id + '/batch', query, header_details)
        json_job_batch_response = json.loads(job_batch_response.text)
        batch_id = json_job_batch_response['id']

        # close the bulk job
        close_body = {'state': 'Closed'}
        json_close_body = json.dumps(close_body, indent=4, separators=(',', ': '))
        close_response = webservice.Tools.post_http_response(
            instance_url + Bulk.base_bulk_uri + Bulk.batch_uri + '/' + job_id, json_close_body, header_details)
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


class Bulk2:
    """
    Bulk API 2.0 provides a simple interface for quickly loading large amounts
    of data into your Salesforce org. Currently csv is the only supported format.

    https://developer.salesforce.com/docs/atlas.en-us.api_bulk_v2.meta/api_bulk_v2/introduction_bulk_api_2.htm
    """
    base_bulk2_uri = '/services/data/v' + API_VERSION + '/jobs/ingest'

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
        header_details = Util.get_standard_header(access_token)

        uri_params = []
        uri_param_string = ""

        if is_pk_chunking_enabled:
            uri_params.append("isPkChunkingEnabled=true")

        if job_type:
            uri_params.append("jobType=" + job_type)

        if query_locator:
            uri_params.append("queryLocator=" + str(query_locator))

        if uri_params:
            uri_param_string = "?" + "&".join(uri_params)

        response = webservice.Tools.get_http_response(instance_url + Bulk2.base_bulk2_uri + uri_param_string,
                                                      header_details)

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
        header_details = Util.get_standard_header(access_token)
        header_details["Content-Type"] = "application/json; charset=UTF-8"
        header_details["Accept"] = "application/json"

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

        json_post_body_data = json.dumps(post_body, indent=4, separators=(',', ': '))
        response = webservice.Tools.post_http_response(instance_url + Bulk2.base_bulk2_uri, json_post_body_data,
                                                       header_details)
        json_response = json.loads(response.text)

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
        header_details = Util.get_standard_header(access_token)
        header_details["Content-Type"] = "text/csv"
        header_details["Accept"] = "application/json"

        response = webservice.Tools.put_http_response(instance_url + Bulk2.base_bulk2_uri + '/' + job_id + '/batches',
                                                      data_set, header_details)

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
        header_details = Util.get_standard_header(access_token)

        request_body = {"state": job_state}

        json_request_body = json.dumps(request_body, indent=4, separators=(',', ': '))
        response = webservice.Tools.patch_http_response(instance_url + Bulk2.base_bulk2_uri + '/' + job_id,
                                                        json_request_body, header_details)
        json_response = json.loads(response.text)

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
        header_details = Util.get_standard_header(access_token)

        response = webservice.Tools.delete_http_response(instance_url + Bulk2.base_bulk2_uri + '/' + job_id, None,
                                                         header_details)

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
        header_details = Util.get_standard_header(access_token)

        response = webservice.Tools.get_http_response(instance_url + Bulk2.base_bulk2_uri + '/' + job_id,
                                                      header_details)
        json_response = json.loads(response.text)

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
                if processed_total == json_response['numberRecordsProcessed']:
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
        header_details = Util.get_standard_header(access_token)

        response = webservice.Tools.get_http_response(
            instance_url + Bulk2.base_bulk2_uri + '/' + job_id + '/successfulResults/', header_details)

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
        header_details = Util.get_standard_header(access_token)

        response = webservice.Tools.get_http_response(
            instance_url + Bulk2.base_bulk2_uri + '/' + job_id + '/failedResults/', header_details)

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
        header_details = Util.get_standard_header(access_token)

        response = webservice.Tools.get_http_response(
            instance_url + Bulk2.base_bulk2_uri + '/' + job_id + '/unprocessedrecords/', header_details)

        return response.text


class Metadata:
    """
    Use Metadata API to retrieve, deploy, create, update or delete customization
    information, such as custom object definitions and page layouts, for your
    organization. This API is intended for managing customizations and for
    building tools that can manage the metadata model, not the data itself.
    """

    @staticmethod
    def get_session_header(session_id):
        """
        Used to get the session header for the given session_id

        Args:
            session_id (str): The session ID that the login call returns.

        Returns:
            object: Returns the session header element for SOAP Metadata
                    requests
        """
        client = Util.get_soap_client(METADATA_WSDL_FILE)
        session_header_element = client.get_element('ns0:SessionHeader')
        session_header = session_header_element(session_id)

        return session_header

    @staticmethod
    def get_call_options(client_name):
        """
        This returns the call options for the soap header

        Args:
            client_name     A value that identifies an API client.

        Returns:
            object: Returns the call options element for SOAP Metadata requests
        """
        client = Util.get_soap_client(METADATA_WSDL_FILE)
        call_options_element = client.get_element('ns0:CallOptions')
        call_options = call_options_element(client_name)

        return call_options

    @staticmethod
    def get_all_or_none_header(all_or_none):
        """
        Indicates whether to roll back all metadata changes when some of the
        records in a call result in failures.

        Args:
            all_or_none (bool): Set to true to cause all metadata changes to be
                                rolled back if any records in the call cause
                                failures. Set to false to enable saving only the
                                records that are processed successfully when
                                other records in the call cause failures.

        Returns:
            object: Returns the AllOrNoneHeader element for SOAP Metadata
                    requests
        """
        client = Util.get_soap_client(METADATA_WSDL_FILE)
        all_or_none_header_element = client.get_element('ns0:AllOrNoneHeader')
        all_or_none_header = all_or_none_header_element(all_or_none)

        return all_or_none_header

    @staticmethod
    def get_debugging_header(categories):
        """
        Specifies that the deployment result will contain the debug log output,
        and specifies the level of detail included in the log. The debug log
        contains the output of Apex tests that are executed as part of a
        deployment.

        Args:
            categories (array): A list of log categories with their associated
                                log levels.

        Returns:
            object: Returns the DebuggingHeader for SOAP Metadata requests
        """
        client = Util.get_soap_client(METADATA_WSDL_FILE)
        debugging_header_element = client.get_element('ns0:DebuggingHeader')
        debugging_header = debugging_header_element(categories, None)

        return debugging_header

    @staticmethod
    def get_soap_headers(session_id, client_name, all_or_none, debug_categories):
        """
        This builds the session header for the Metadata requests

        Args:
            session_id (str): The session ID that the login call returns.
            client_name (str): A value that identifies an API client.
            all_or_none (bool): Set to true to cause all metadata changes to be
                                rolled back if any records in the call cause
                                failures. Set to false to enable saving only the
                                records that are processed successfully when
                                other records in the call cause failures.
            debug_categories (array): A list of log categories with their
                                      associated log levels.

        Returns:
            object: Returns the headers for SOAP Metadata requests
        """
        soap_headers = {}
        soap_headers['SessionHeader'] = Metadata.get_session_header(session_id)

        if client_name != None:
            soap_headers['CallOptions'] = Metadata.get_call_options(client_name)

        if all_or_none != None:
            soap_headers['AllOrNoneHeader'] = Metadata.get_all_or_none_header(all_or_none)

        if debug_categories != None:
            soap_headers['DebuggingHeader'] = Metadata.get_debugging_header(debug_categories)

        return soap_headers

    @staticmethod
    def get_metadata(full_name):
        """
        This is the base class for all metadata types. You cannot edit this
        object. A component is an instance of a metadata type.
        Metadata is analogous to sObject, which represents all standard objects.
        Metadata represents all components and fields in Metadata API. Instead
        of identifying each component with an ID, each custom object or custom
        field has a unique fullName, which must be distinct from standard object
        names, as it must be when you create custom objects or custom fields in
        the Salesforce user interface.

        Args:
            full_name (str): Required. The name of the component. If a field,
                             the name must specify the parent object, for
                             example Account.FirstName. The __c suffix must be
                             appended to custom object names and custom field
                             names when you are setting the fullName. For
                             example, a custom field in a custom object could
                             have a fullName of MyCustomObject__c.MyCustomField__c.
                             To reference a component in a package, prepend the
                             package’s namespace prefix to the component name in
                             the fullName field. Use the following syntax:
                             namespacePrefix__ComponentName. For example, for the
                             custom field component MyCustomObject__c.MyCustomField__c
                             and the namespace MyNS, the full name is
                             MyNS__MyCustomObject__c.MyCustomField__c.

        Returns:
            object: Returns the metadata object
        """
        client = Util.get_soap_client(METADATA_WSDL_FILE)
        metadata_type = client.get_type('ns0:Metadata')
        metadata = metadata_type(full_name)

        return metadata

    @staticmethod
    def get_package_type_members(member_name, member_list):
        """
        This builds the list of members for a specific type. For example this
        will store the list of all the ApexClass members you want to reference.

        Args:
            member_name (str): This is the Metadata type being referenced.
                               A list of types can be found here: https://
                               developer.salesforce.com/docs/atlas.en-us.
                               api_meta.meta/api_meta/meta_types_list.htm
            member_list (array): An array of the members you're working with in
                                 the package.

        Returns:
            object: Returns the package type members for making SOAP Metadata
                    requests
        """
        package_type_members = {}
        package_type_members['name'] = member_name
        package_type_members['members'] = member_list

        return package_type_members

    @staticmethod
    def get_client_service(metadata_url):
        """
        This method builds the client service for the Metadata API

        Args:
            metadata_url (str): The Url used to send this request to

        Returns:
            Returns the client service for SOAP Metadata requests
        """
        soap_client_service = Util.get_soap_client_service(METADATA_WSDL_FILE, METADATA_SERVICE_BINDING, metadata_url)

        return soap_client_service

    @staticmethod
    def get_package(**kwargs):
        """
        Specifies which metadata components to retrieve as part of a retrieve()
        call or defines a package of components.

        Args:
            full_name (str): The package name used as a unique identifier for
                             API access. The fullName can contain only
                             underscores and alphanumeric characters. It must be
                             unique, begin with a letter, not include spaces,
                             not end with an underscore, and not contain two
                             consecutive underscores. This field is inherited
                             from the Metadata component.
            api_access_level (str): Package components have access via dynamic
                                    Apex and the API to standard and custom
                                    objects in the organization where they are
                                    installed. Administrators who install
                                    packages may wish to restrict this access
                                    after installation for improved security.
                                    The valid values are:
                                    * Unrestricted—Package components have
                                        the same API access to standard objects
                                        as the user who is logged in when the
                                        component sends a request to the API.
                                    * Restricted—The administrator can select
                                        which standard objects the components
                                        can access. Further, the components in
                                        restricted packages can only access
                                        custom objects in the current package
                                        if the user's permissions allow access
                                        to them.
                                    For more information, see “About API and
                                    Dynamic Apex Access in Packages” in the
                                    Salesforce online help.
            description (str): A short description of the package.
            namespace_prefix (str): The namespace of the developer organization
                                     where the package was created.
            object_permissions (array): Indicates which objects are accessible to
                                        the package, and the kind of access
                                        available (create, read, update, delete)
            package_type (str): Reserved for future use.
            post_install_class (str): The name of the Apex class that specifies
                                      the actions to execute after the package
                                      has been installed or upgraded. The Apex
                                      class must be a member of the package and
                                      must implement the Apex InstallHandler
                                      interface. In patch upgrades, you can't
                                      change the class name in this field but
                                      you can change the contents of the Apex
                                      class. The class name can be changed in
                                      major upgrades. This field is available in
                                      API version 24.0 and later.
            setup_web_link (str): The weblink used to describe package
                                  installation.
            types (array): The type of component being retrieved. You can build
                           the types with the get_package_type_members() method.
            uninstall_class (str): The name of the Apex class that specifies
                                   the actions to execute after the package has
                                   been uninstalled. The Apex class must be a
                                   member of the package and must implement the
                                   Apex UninstallHandler interface. In patch
                                   upgrades, you can't change the class name in
                                   this field but you can change the contents of
                                   the Apex class. The class name can be changed
                                   in major upgrades.
                                   This field is available in API version 25.0
                                   and later.
            version (str): Required. The version of the component type.

        Returns:
            object: Returns the package that was requested.
        """
        if kwargs.get('version') is None:
            print('The version parameter is required to create a package.')
            sys.exit(0)

        client = Util.get_soap_client(METADATA_WSDL_FILE)
        package_type = client.get_type('ns0:Package')
        this_package = package_type(
            kwargs.get('full_name'),
            kwargs.get('api_access_level'),
            kwargs.get('description'),
            kwargs.get('namespace_prefix'),
            kwargs.get('object_permissions'),
            kwargs.get('package_type'),
            kwargs.get('post_install_class'),
            kwargs.get('setup_web_link'),
            kwargs.get('types'),
            kwargs.get('uninstall_class'),
            kwargs.get('version')
        )

        return this_package

    @staticmethod
    def get_deploy_options(**kwargs):
        """
        The options that can be set for deploying a metadata package

        Args:
            allow_missing_files (bool): If files that are specified in package.xml
                                        are not in the .zip file, specifies whether
                                        a deployment can still succeed.
                                        Do not set this argument for deployment to
                                        production orgs.
            auto_update_package (bool): If a file is in the .zip file but not
                                        specified in package.xml, specifies whether
                                        the file is automatically added to the
                                        package. A retrieve() is issued with the
                                        updated package.xml that includes the .zip
                                        file.
                                        Do not set this argument for deployment to
                                        production orgs.
            check_only (bool): Defaults to false. Set to true to perform a
                               test deployment (validation) of components
                               without saving the components in the target
                               org. A validation enables you to verify the
                               results of tests that would be generated in
                               a deployment, but doesn’t commit any changes.
                               After a validation finishes with passing tests,
                               it might qualify for deployment without
                               rerunning tests. See deployRecentValidation().
            ignore_warnings (bool): Indicates whether a warning should allow a
                                    deployment to complete successfully (true)
                                    or not (false). Defaults to false.
                                    The DeployMessage object for a warning
                                    contains the following values:
                                        -problemType—Warning
                                        -problem—The text of the warning.
                                    If a warning occurs and ignoreWarnings is
                                    set to true, the success field in
                                    DeployMessage is true. If ignoreWarnings is
                                    set to false, success is set to false and
                                    the warning is treated like an error.
            perform_retrieve (bool): Indicates whether a retrieve() call is
                                     performed immediately after the deployment
                                     (true) or not (false). Set to true in order
                                     to retrieve whatever was just deployed.
            purge_on_delete (bool): If true, the deleted components in the
                                    destructiveChanges.xml manifest file aren't
                                    stored in the Recycle Bin. Instead, they
                                    become immediately eligible for deletion.
                                    This option only works in Developer Edition
                                    or sandbox orgs; it doesn't work in
                                    production orgs.
            rollback_on_error (bool): Indicates whether any failure causes a
                                      complete rollback (true) or not (false). If
                                      false, whatever actions can be performed
                                      without errors are performed, and errors are
                                      returned for the remaining actions. This
                                      parameter must be set to true if you are
                                      deploying to a production org. The default
                                      is false.
            run_tests (array): A list of Apex tests to run during
                               deployment. Specify the class name, one name
                               per instance. The class name can also
                               specify a namespace with a dot notation. For
                               more information, see Running a Subset of
                               Tests in a Deployment.
                               To use this option, set testLevel to
                               RunSpecifiedTests.
            single_package (bool): Indicates whether the specified .zip file
                                   points to a directory structure with a
                                   single package (true) or a set of packages
                                   (false).
            test_level (str): Optional. Specifies which tests are run as
                              part of a deployment. The test level is
                              enforced regardless of the types of
                              components that are present in the deployment
                              package. Valid values are:
                                  -NoTestRun—No tests are run. This test
                                  level applies only to deployments to
                                  development environments, such as
                                  sandbox, Developer Edition, or trial
                                  organizations. This test level is the
                                  default for development environments.
                                  -RunSpecifiedTests—Only the tests that
                                  you specify in the runTests option are
                                  run. Code coverage requirements differ
                                  from the default coverage requirements
                                  when using this test level. Each class
                                  and trigger in the deployment package
                                  must be covered by the executed tests
                                  for a minimum of 75% code coverage.
                                  This coverage is computed for each
                                  class and trigger individually and is
                                  different than the overall coverage
                                  percentage.
                                  -RunLocalTests—All tests in your org are
                                  run, except the ones that originate
                                  from installed managed packages. This
                                  test level is the default for production
                                  deployments that include Apex classes
                                  or triggers.
                                  -RunAllTestsInOrg—All tests are run. The
                                  tests include all tests in your org,
                                  including tests of managed packages.

        Returns:
            object: Returns the deploy options object for creating SOAP Metadata
                    requests
        """
        client = Util.get_soap_client(METADATA_WSDL_FILE)
        deploy_options_type = client.get_type('ns0:DeployOptions')
        deploy_options = deploy_options_type(
            kwargs.get('allow_missing_files'),
            kwargs.get('auto_update_package'),
            kwargs.get('check_only'),
            kwargs.get('ignore_warnings'),
            kwargs.get('perform_retrieve'),
            kwargs.get('purge_on_delete'),
            kwargs.get('rollback_on_error'),
            kwargs.get('run_tests'),
            kwargs.get('single_package'),
            kwargs.get('test_level')
        )

        return deploy_options

    @staticmethod
    def get_retrieve_request(**kwargs):
        """
        This is the package of data needed to retrieve metadata

        Args:
            api_version (dbl): Required. The API version for the retrieve
                               request. The API version determines the fields
                               retrieved for each metadata type. For example,
                               an icon field was added to the CustomTab for
                               API version 14.0. If you retrieve components
                               for version 13.0 or earlier, the components
                               will not include the icon field.
            package_names (array): A list of package names to be retrieved. If
                                   you are retrieving only unpackaged components,
                                   do not specify a name here. You can retrieve
                                   packaged and unpackaged components in the
                                   same retrieve.
            single_package (bool): Specifies whether only a single package is
                                   being retrieved (true) or not (false). If
                                   false, then more than one package is being
                                   retrieved.
            specific_files (array): A list of file names to be retrieved. If a
                                    value is specified for this property,
                                    package_names must be set to null and
                                    single_package must be set to true.
            unpackaged (array): A list of components to retrieve that are not
                                in a package. You can build the package using
                                the get_package() method.

        Returns:
            object: Returns the retrieve request used to create SOAP Metadata
                    requests
        """
        if kwargs.get('api_version') is None:
            print('The version parameter is required to create a package.')
            sys.exit(0)

        client = Util.get_soap_client(METADATA_WSDL_FILE)
        retrieveRequest_type = client.get_type('ns0:RetrieveRequest')
        this_retrieve_request = retrieveRequest_type(
            kwargs.get('api_version'),
            kwargs.get('package_names'),
            kwargs.get('single_package'),
            kwargs.get('specific_files'),
            kwargs.get('unpackaged')
        )

        return this_retrieve_request

    @staticmethod
    def get_list_metadata_query(folder, metadata_type):
        list_metadata_query_type = client.get_type('ns0:ListMetadataQuery')
        metadata_query = list_metadata_query_type(folder, metadata_type)

        return metadata_query

    @staticmethod
    def retrieve(retrieve_request, session_id, metadata_url, client_name):
        """
        This returns the async result of a retrieve request that can then be
        used to check the retrieve status

        Args:
            retrieve_request (object): The request settings which can be created
                                       using the get_retrieve_request() method
            session_id (str): The session ID that the login call returns.
            metadata_url (str): The Url used to send this request to
            client_name (str): A value that identifies an API client. This is
                               used for partner applications
        """
        soap_headers = Metadata.get_soap_headers(session_id, client_name, None, None)

        client_service = Metadata.get_client_service(metadata_url)
        this_retrieve = client_service.retrieve(retrieve_request, _soapheaders=soap_headers)

        return this_retrieve

    @staticmethod
    def check_retrieve_status(async_process_id, include_zip, session_id, metadata_url, client_name):
        """
        This checks the status of the retrieve request. You can have the response
        include a zip file if you wish, or you can set that to false and get the
        zip in a later response

        Args:
            async_process_id (str): Required. The ID of the component that’s
                                    being deployed or retrieved.
            include_zip (bool): This tells the process whether or not to
                                include the zip file in the result or. Starting
                                with API version 34.0, pass a boolean value for
                                the include_zip argument of checkRetrieveStatus()
                                to indicate whether to retrieve the zip file.
                                The include_zip argument gives you the option to
                                retrieve the file in a separate process after
                                the retrieval operation is completed.
            session_id (str): The session ID that the login call returns.
            metadata_url (str): The Url used to send this request to
            client_name (str): A value that identifies an API client. This is
                               used for partner applications.

        Returns:
            object: Returns the status of the existing metadata retrieve request
        """
        soap_headers = Metadata.get_soap_headers(session_id, client_name, None, None)

        client_service = Metadata.get_client_service(metadata_url)
        this_retrieve_status = client_service.checkRetrieveStatus(async_process_id, include_zip,
                                                                  _soapheaders=soap_headers)

        return this_retrieve_status

    @staticmethod
    def cancel_deploy(deploy_id, session_id, metadata_url, client_name):
        """
        This method cancels the deploy

        Args:
            deploy_id (str): The Id returned from the deploy request
            session_id (str): The session ID that the login call returns.
            metadata_url (str): The Url used to send this request to
            client_name (str): A value that identifies an API client. This is
                               used for partner applications

        Returns:
            object: Returns the result of the cancel deploy request
        """
        soap_headers = Metadata.get_soap_headers(session_id, client_name, None, None)

        client_service = Metadata.get_client_service(metadata_url)
        cancel_deploy_result = client_service.cancelDeploy(deploy_id, _soapheaders=soap_headers)

        return cancel_deploy_result

    @staticmethod
    def check_deploy_status(deploy_id, include_details, session_id, metadata_url, client_name):
        """
        This method checks the status of the requested deploy

        Args:
            deploy_id             The Id returned from the deploy request
            include_details       Sets the DeployResult object to include
                                    DeployDetails information ((true) or not
                                    (false). The default is false. Available in
                                    API version 29.0 and later.
            session_id            The session ID that the login call returns.
            metadata_url          The Url used to send this request to
            client_name           A value that identifies an API client. This is
                                    used for partner applications
        """
        soap_headers = Metadata.get_soap_headers(session_id, client_name, None, None)

        client_service = Metadata.get_client_service(metadata_url)
        check_deploy_result = client_service.checkDeployStatus(deploy_id, include_details, _soapheaders=soap_headers)

        return check_deploy_result

    @staticmethod
    def create_metadata(metadata_list, session_id, metadata_url, client_name, all_or_none):
        """
        Adds one or more new metadata components to your organization synchronously.

        Args:
            metadata_list (array): Array of one or more metadata components.
                                   Limit: 10. (For CustomMetadata and
                                   CustomApplication only, the limit is 200.)
                                   You must submit arrays of only one type of
                                   component. For example, you can submit an
                                   array of 10 custom objects or 10 profiles,
                                   but not a mix of both types.
            session_id (str): The session ID that the login call returns.
            metadata_url (str): The Url used to send this request to
            client_name (str): A value that identifies an API client. This is
                               used for partner applications
            all_or_none (bool): Set to true to cause all metadata changes to
                                be rolled back if any records in the call
                                cause failures. Set to false to enable saving
                                only the records that are processed
                                successfully when other records in the call
                                cause failures.

        Returns:
            object: Returns the results of the create metadata request
        """
        soap_headers = Metadata.get_soap_headers(session_id, client_name, all_or_none, None)

        client_service = Metadata.get_client_service(metadata_url)
        create_metadata_result = client_service.createMetadata(metadata_list, _soapheaders=soap_headers)

        return create_metadata_result

    @staticmethod
    def delete_metadata(metadata_type, full_names, session_id, metadata_url, client_name, all_or_none):
        """
        Deletes one or more metadata components from your organization synchronously.

        Args:
            metadata_type (str): The metadata type of the components to delete.
            full_names (array): Array of full names of the components to delete.
                                Limit: 10. (For CustomMetadata and
                                CustomApplication only, the limit is 200.)
                                You must submit arrays of only one type of
                                component. For example, you can submit an
                                array of 10 custom objects or 10 profiles, but
                                not a mix of both types.
            session_id (str): The session ID that the login call returns.
            metadata_url (str): The Url used to send this request to
            client_name (str): A value that identifies an API client. This is
                               used for partner applications
            all_or_none (bool): Set to true to cause all metadata changes to
                                be rolled back if any records in the call
                                cause failures. Set to false to enable saving
                                only the records that are processed
                                successfully when other records in the call
                                cause failures.

        Returns:
            object: Returns the result of the delete metadata request
        """
        soap_headers = Metadata.get_soap_headers(session_id, client_name, all_or_none, None)

        client_service = Metadata.get_client_service(metadata_url)
        delete_metadata_result = client_service.deleteMetadata(metadata_type, full_names, _soapheaders=soap_headers)

        return delete_metadata_result

    @staticmethod
    def deploy(zip_file, deploy_options, session_id, metadata_url, client_name, debug_categories):
        """
        Uses file representations of components to create, update, or delete those
        components in a Salesforce org.

        Args:
            zip_file (file): Base 64-encoded binary data. Client applications
                             must encode the binary data as base64.
            deploy_options (object): Encapsulates options for determining which
                                     packages or files are deployed.
            session_id (str): The session ID that the login call returns.
            metadata_url (str): The Url used to send this request to
            client_name (str): A value that identifies an API client. This is
                               used for partner applications
            debug_categories (array): A list of log categories with their
                                      associated log levels.

        Returns:
            object: Returns the result of a Metadata deploy request
        """
        soap_headers = Metadata.get_soap_headers(session_id, client_name, None, debug_categories)

        client_service = Metadata.get_client_service(metadata_url)
        deploy_result = client_service.deploy(zip_file, deploy_options, _soapheaders=soap_headers)

        return deploy_result

    @staticmethod
    def deploy_recent_validation(validation_id, session_id, metadata_url, client_name, debug_categories):
        soap_headers = Metadata.get_soap_headers(session_id, client_name, None, debug_categories)

        client_service = Metadata.get_client_service(metadata_url)
        deploy_validation_result = client_service.deployRecentValidation(validation_id, _soapheaders=soap_headers)

        return deploy_validation_result

    @staticmethod
    def describe_metadata(as_of_version, session_id, metadata_url, client_name):
        soap_headers = Metadata.get_soap_headers(session_id, client_name, None, None)

        client_service = Metadata.get_client_service(metadata_url)
        describe_metadata_result = client_service.describeMetadata(as_of_version, _soapheaders=soap_headers)

        return describe_metadata_result

    @staticmethod
    def describe_value_type(value_type, session_id, metadata_url):
        soap_headers = Metadata.get_soap_headers(session_id, None, None, None)

        client_service = Metadata.get_client_service(metadata_url)
        describe_value_type = client_service.describeValueType(value_type, _soapheaders=soap_headers)

        return describe_value_type

    @staticmethod
    def list_metadata(list_metadata_query, as_of_version, session_id, metadata_url, client_name):
        soap_headers = Metadata.get_soap_headers(session_id, client_name, None, None)

        client_service = Metadata.get_client_service(metadata_url)
        list_metadata_result = client_service.listMetadata(list_metadata_query, as_of_version,
                                                           _soapheaders=soap_headers)

        return list_metadata_result

    @staticmethod
    def read_metadata(metadata_type, full_names, session_id, metadata_url, client_name):
        soap_headers = Metadata.get_soap_headers(session_id, client_name, None, None)

        client_service = Metadata.get_client_service(metadata_url)
        read_metadata_result = client_service.readMetadata(metadata_type, full_names, _soapheaders=soap_headers)

        return read_metadata_result

    @staticmethod
    def rename_metadata(metadata_type, old_full_name, new_full_name, session_id, metadata_url, client_name):
        soap_headers = Metadata.get_soap_headers(session_id, client_name, None, None)

        client_service = Metadata.get_client_service(metadata_url)
        rename_metadata_result = client_service.renameMetadata(metadata_type, old_full_name, new_full_name,
                                                               _soapheaders=soap_headers)

        return rename_metadata_result

    @staticmethod
    def update_metadata(metadata_list, session_id, metadata_url, client_name, all_or_none):
        soap_headers = Metadata.get_soap_headers(session_id, client_name, all_or_none, None)

        client_service = Metadata.get_client_service(metadata_url)
        update_metadata_result = client_service.updateMetadata(metadata_list, _soapheaders=soap_headers)

        return update_metadata_result

    @staticmethod
    def upsert_metadata(metadata_list, session_id, metadata_url, client_name, all_or_none):
        soap_headers = Metadata.get_soap_headers(session_id, client_name, all_or_none, None)

        client_service = Metadata.get_client_service(metadata_url)
        upsert_metadata_result = client_service.upsertMetadata(metadata_list, _soapheaders=soap_headers)

        return upsert_metadata_result
