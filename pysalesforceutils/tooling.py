#!/usr/bin/python3

"""
Salesforce Tooling API.
"""

import urllib.parse

import pysalesforceutils
from .util import _rest_json


class Tooling:
    """
    The purpose of this class is to expose the Salesforce Tooling API methods
    """
    # no longer used by the methods in this class. Kept so existing code that
    # reads it doesn't break.
    base_tooling_uri = '/services/data/v' + pysalesforceutils.API_VERSION + '/tooling'

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
        completions_uri = '/tooling/completions?type='
        url_encoded_type = urllib.parse.quote(completions_type)

        json_response = _rest_json('GET', completions_uri + url_encoded_type, access_token, instance_url)

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
        execute_anonymous_uri = '/tooling/executeAnonymous/?anonymousBody='
        url_encoded_code = urllib.parse.quote(code_string)

        json_response = _rest_json('GET', execute_anonymous_uri + url_encoded_code, access_token, instance_url)

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
        query_uri = '/tooling/query/?q='
        url_encoded_query = urllib.parse.quote(query_string)

        json_response = _rest_json('GET', query_uri + url_encoded_query, access_token, instance_url)

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
        test_async_uri = '/tooling/runTestsAsynchronous/'

        data_body = {}

        if class_ids != None:
            data_body['classids'] = class_ids

        if suite_ids != None:
            data_body['suiteids'] = suite_ids

        if max_failed_tests != None:
            data_body['maxFailedTests'] = max_failed_tests

        if test_level != None:
            data_body['testLevel'] = test_level

        json_response = _rest_json('POST', test_async_uri, access_token, instance_url, data_body)

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
        test_async_uri = '/tooling/runTestsAsynchronous/'
        data_body = {'tests': test_array}

        json_response = _rest_json('POST', test_async_uri, access_token, instance_url, data_body)

        return json_response
