#!/usr/bin/python3

"""
Builds the subrequests used by the composite methods on the Standard class.
"""

import urllib.parse

import pysalesforceutils


def _quote_reference(value):
    """
    URL encodes a value so it can only be a single URL path segment, but
    leaves references to other subrequests like @{reference_id.id} as they are.
    """
    if value in ('.', '..'):
        raise ValueError('Invalid URL path value: {}'.format(value))

    return urllib.parse.quote(value, safe='@{}')


class Composite:
    """
    This class builds the subrequests for Standard.composite_request,
    Standard.composite_batch_request and Standard.graph_composite_request, so
    they don't need to be written by hand. The methods only build the dicts
    for the request, they don't call Salesforce. For example:

        subrequests = [
            Composite.create('new_account', 'Account', {'Name': 'Cloudy Consulting'}),
            Composite.create('new_contact', 'Contact', {'LastName': 'Cashman', 'AccountId': '@{new_account.id}'})
        ]

        Standard.composite_request(subrequests, True, access_token, instance_url)

    The reference_id is the name used to find the result of the subrequest in
    the response, and to use its output in a later subrequest, e.g.
    '@{new_account.id}'. It can only contain letters, numbers and underscores.
    """

    @staticmethod
    def request(reference_id, method, path, body=None):
        """
        Builds a subrequest for any REST API resource. The other methods in
        this class use this one.

        Args:
            reference_id (str): The name used to refer to this subrequest
            method (str): The request type: GET, POST, PATCH, PUT or DELETE
            path (str): The part of the URL that comes after
                        /services/data/vXX.X, e.g. '/sobjects/Account/'
            body (object): The python object to send as the request body.
                           Defaults to None

        Returns:
            dict: Returns the subrequest.
        """
        subrequest = {'method': method, 'url': '/services/data/v' + pysalesforceutils.API_VERSION + path,
                      'referenceId': reference_id}

        if body != None:
            subrequest['body'] = body

        return subrequest

    @staticmethod
    def create(reference_id, object_name, record_json):
        """
        Builds a subrequest that creates a record.

        Args:
            reference_id (str): The name used to refer to this subrequest
            object_name (str): The API name of the object.
            record_json (dict): The fields to set on the new record, e.g.
                                {'Name': 'Cloudy Consulting'}

        Returns:
            dict: Returns the subrequest.
        """
        return Composite.request(reference_id, 'POST', '/sobjects/' + _quote_reference(object_name) + '/',
                                 record_json)

    @staticmethod
    def update(reference_id, object_name, record_id, record_json):
        """
        Builds a subrequest that updates a record.

        Args:
            reference_id (str): The name used to refer to this subrequest
            object_name (str): The API name of the object.
            record_id (str): The record Id, or a reference to the output of
                             an earlier subrequest, e.g. '@{new_account.id}'
            record_json (dict): The fields to update on the record

        Returns:
            dict: Returns the subrequest.
        """
        return Composite.request(reference_id, 'PATCH',
                                 '/sobjects/' + _quote_reference(object_name) + '/' + _quote_reference(record_id),
                                 record_json)

    @staticmethod
    def upsert(reference_id, object_name, external_id_field_name, external_id, record_json):
        """
        Builds a subrequest that creates or updates a record based on the
        value of its external Id field.

        Args:
            reference_id (str): The name used to refer to this subrequest
            object_name (str): The API name of the object.
            external_id_field_name (str): The API name of the external Id field
            external_id (str): The external Id value of the record
            record_json (dict): The fields to set on the record. Don't include
                                the external Id field itself.

        Returns:
            dict: Returns the subrequest.
        """
        return Composite.request(reference_id, 'PATCH',
                                 '/sobjects/' + _quote_reference(object_name) + '/' +
                                 _quote_reference(external_id_field_name) + '/' + _quote_reference(str(external_id)),
                                 record_json)

    @staticmethod
    def delete(reference_id, object_name, record_id):
        """
        Builds a subrequest that deletes a record.

        Args:
            reference_id (str): The name used to refer to this subrequest
            object_name (str): The API name of the object.
            record_id (str): The record Id, or a reference to the output of
                             an earlier subrequest, e.g. '@{new_account.id}'

        Returns:
            dict: Returns the subrequest.
        """
        return Composite.request(reference_id, 'DELETE',
                                 '/sobjects/' + _quote_reference(object_name) + '/' + _quote_reference(record_id))

    @staticmethod
    def get(reference_id, object_name, record_id, field_list_string=None):
        """
        Builds a subrequest that retrieves a record.

        Args:
            reference_id (str): The name used to refer to this subrequest
            object_name (str): The API name of the object.
            record_id (str): The record Id, or a reference to the output of
                             an earlier subrequest, e.g. '@{new_account.id}'
            field_list_string (str): List of comma separated values for fields
                                     to retrieve. Defaults to None

        Returns:
            dict: Returns the subrequest.
        """
        get_row_uri = '/sobjects/' + _quote_reference(object_name) + '/' + _quote_reference(record_id)

        if field_list_string != None:
            get_row_uri = get_row_uri + '?fields=' + urllib.parse.quote(field_list_string, safe=',')

        return Composite.request(reference_id, 'GET', get_row_uri)

    @staticmethod
    def query(reference_id, query_string):
        """
        Builds a subrequest that executes a SOQL query.

        Args:
            reference_id (str): The name used to refer to this subrequest
            query_string (str): The query you'd like to run. It can refer to
                                the output of an earlier subrequest, e.g.
                                "SELECT Id FROM Contact WHERE AccountId = '@{new_account.id}'"

        Returns:
            dict: Returns the subrequest.
        """
        return Composite.request(reference_id, 'GET', '/query/?q=' + urllib.parse.quote(query_string, safe='/@{}'))

    @staticmethod
    def graph(graph_id, subrequests):
        """
        Builds one graph for Standard.graph_composite_request, e.g.:
            request_body = {'graphs': [Composite.graph('graph1', subrequests)]}

        Args:
            graph_id (str): The name used to find this graph in the response
            subrequests (list): The list of subrequests in the graph

        Returns:
            dict: Returns the graph.
        """
        return {'graphId': graph_id, 'compositeRequest': subrequests}
