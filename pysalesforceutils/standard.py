#!/usr/bin/python3

"""
Salesforce standard REST API.
"""

import json
import os
import urllib.parse
from mimetypes import MimeTypes

import pysalesforceutils
from . import webservice
from .util import Util, _quote_path, _rest_json, _rest_request


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
            instance_url + Standard.base_standard_uri + 'v' + _quote_path(version_num_string) + '/', header_details)
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
        get_row_uri = '/sobjects/' + _quote_path(object_name) + '/' + _quote_path(record_id)

        if field_list_string != None:
            get_row_uri = get_row_uri + '?fields=' + urllib.parse.quote(field_list_string, safe=',')

        json_response = _rest_json('GET', get_row_uri, access_token, instance_url)

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
            "Document": "Body",
            "ContentNote": "Content"
        }

        get_row_uri = '/sobjects/' + _quote_path(object_name) + '/' + _quote_path(record_id) + '/' + object_to_blob_map[object_name]

        response = _rest_request('GET', get_row_uri, access_token, instance_url)

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
        post_row_uri = '/sobjects/'+ _quote_path(object_name) + '/'
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
            instance_url + Standard.base_standard_uri + 'v' + pysalesforceutils.API_VERSION + post_row_uri, None,
            header_details, multipart_files)
        response_text = ""

        if response.status_code == 204:
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
        post_row_uri = '/sobjects/' + _quote_path(object_name) + '/'
        headers = {"Sforce-Auto-Assign": "true" if run_assignment_rules else "false"}

        response = _rest_request('POST', post_row_uri, access_token, instance_url, record_json, headers)
        response_text = ""

        if response.status_code == 204:
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

        get_row_uri = '/composite/sobjects/' + _quote_path(object_name)

        get_rows_uri = get_row_uri + '?ids=' + urllib.parse.quote(record_id_list_string, safe=',')

        if field_list_string != None:
            get_rows_uri = get_rows_uri + '&fields=' + urllib.parse.quote(field_list_string, safe=',')

        json_response = _rest_json('GET', get_rows_uri, access_token, instance_url)

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
        headers = {"Sforce-Auto-Assign": "true" if run_assignment_rules else "false"}

        request_body = {}
        request_body["allOrNone"] = all_or_none
        request_body["records"] = records

        return _rest_json('POST', post_rows_uri, access_token, instance_url, request_body, headers)

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
        patch_row_uri = '/sobjects/' + _quote_path(object_name) + '/' + _quote_path(record_id)
        headers = {"Sforce-Auto-Assign": "true" if run_assignment_rules else "false"}

        response = _rest_request('PATCH', patch_row_uri, access_token, instance_url, record_json, headers)
        response_text = ""

        if response.status_code == 204:
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
                                          "attributes" : {"type" : "Account", "id" : "001xx000003DGb2AAG"},
                                          "Name" : "example.com",
                                          "BillingCity" : "San Francisco"
                                       }, {
                                          "attributes" : {"type" : "Contact", "id": "003xx000004TmiQAAS"},
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
        headers = {"Sforce-Auto-Assign": "true" if run_assignment_rules else "false"}

        request_body = {}
        request_body["allOrNone"] = all_or_none
        request_body["records"] = records

        return _rest_json('PATCH', patch_rows_uri, access_token, instance_url, request_body, headers)

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
        patch_rows_uri = "/composite/sobjects/" + _quote_path(object_api_name) + "/" + _quote_path(external_id_field_name)
        headers = {"Sforce-Auto-Assign": "true" if run_assignment_rules else "false"}

        request_body = {}
        request_body["allOrNone"] = all_or_none
        request_body["records"] = records

        return _rest_json('PATCH', patch_rows_uri, access_token, instance_url, request_body, headers)

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

        delete_params = "?ids=" + ",".join(_quote_path(record_id) for record_id in record_ids)

        if all_or_none:
            delete_params += "&allOrNone=true"
        else:
            delete_params += "&allOrNone=false"

        return _rest_json('DELETE', delete_rows_uri + delete_params, access_token, instance_url)

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
        url_encoded_query = urllib.parse.quote(query_string)

        json_response = _rest_json('GET', query_uri + url_encoded_query, access_token, instance_url)

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
        url_encoded_query = urllib.parse.quote(query_string)

        json_response = _rest_json('GET', query_uri + url_encoded_query, access_token, instance_url)

        return json_response
    
    @staticmethod
    def search(search_string, access_token, instance_url):
        """
        Executes the specified SOSL search. If the search results are too large,
        the response contains the first batch of results and a search identifier
        in the nextRecordsUrl field of the response. The identifier can be used
        in an additional request to retrieve the next batch. The difference
        between this and search is that search all can retrieve deleted records.

        Args:
            search_string (str): This search you'd like to run
            access_token (str): This is the access_token value received from the
                                login response
            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            object: returns the search results, if they are too large, then it
                    will also return a nextRecordsUrl to get more records.

        """
        search_uri = '/search/?q='
        url_encoded_search = urllib.parse.quote(search_string)

        json_response = _rest_json('GET', search_uri + url_encoded_search, access_token, instance_url)

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
        query_uri = f'/sobjects/User/{_quote_path(user_id)}/password'

        json_response = _rest_json('DELETE', query_uri, access_token, instance_url)

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

        json_response = _rest_json('GET', query_uri, access_token, instance_url)

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
        request_body = {}
        request_body['body'] = {}
        request_body['body']["messageSegments"] = [{"type": "Mention", "id": mention_id}, {'type': 'Text', "text": text}]
        request_body["feedElementType"] = "FeedItem"
        request_body["subjectId"] = subject_id

        json_response = _rest_json('POST', query_uri, access_token, instance_url, request_body)

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
        get_updated_uri = '/sobjects/' + _quote_path(object_name) + '/updated/?start=' + \
            urllib.parse.quote(start_date_time.strftime('%Y-%m-%dT%H:%M:%SZ')) + '&end=' + \
            urllib.parse.quote(end_date_time.strftime('%Y-%m-%dT%H:%M:%SZ'))

        json_response = _rest_json('GET', get_updated_uri, access_token, instance_url)

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
        retrieve_uri = '/composite/sobjects/' + _quote_path(object_name)

        request_body = {}
        request_body['ids'] = ids
        request_body['fields'] = fields

        json_response = _rest_json('POST', retrieve_uri, access_token, instance_url, request_body)

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
        get_deleted_uri = '/sobjects/' + _quote_path(object_name) + '/deleted/?start=' + \
            urllib.parse.quote(start_date_time.strftime('%Y-%m-%dT%H:%M:%SZ')) + '&end=' + \
            urllib.parse.quote(end_date_time.strftime('%Y-%m-%dT%H:%M:%SZ'))

        json_response = _rest_json('GET', get_deleted_uri, access_token, instance_url)

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

        json_response = _rest_json('POST', graph_uri, access_token, instance_url, request_body)

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
                given object. Returns None if modified_since_date was
                provided and the object has not changed since then.
        """
        describe_uri = "/sobjects/{}/describe/".format(_quote_path(object_name))

        headers = {}

        if modified_since_date:
            modified_since_date = modified_since_date.strftime('%a, %d %b %Y %H:%M:%S GMT')
            headers["If-Modified-Since"] = modified_since_date

        response = _rest_request('GET', describe_uri, access_token, instance_url, None, headers)

        # 304 Not Modified has no response body
        if response.status_code == 304:
            return None

        json_response = json.loads(response.text)

        return json_response
