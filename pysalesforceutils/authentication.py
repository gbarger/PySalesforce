#!/usr/bin/python3

"""
Log in and out of Salesforce.
"""

import json

import pysalesforceutils
from . import webservice
from .util import Util


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
        wsdl_file = pysalesforceutils.PARTNER_WSDL_FILE

        if not (is_production):
            wsdl_file = pysalesforceutils.PARTNER_SANDBOX_WSDL_FILE

        client = Util.get_soap_client(wsdl_file)
        soap_headers = Authentication.get_soap_headers(org_id, portal_id, client_name, default_ns)
        login_result = client.service.login(login_username, login_password, _soapheaders=soap_headers)

        return login_result
