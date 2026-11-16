#!/usr/bin/python3

"""
Log in and out of Salesforce.
"""

import json
import time

import pysalesforceutils
from .util import Util, _Request, _api_method

try:
    import jwt
except ImportError:
    jwt = None


class Authentication:
    """
    The Authentication class is used to log in and out of Salesforce
    """

    @staticmethod
    @_api_method
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

        response = yield _Request(requestType='POST', URL=base_oauth_url, data_body=login_body_data,
                                  header_details='')

        try:
            json_response = json.loads(response.text)
        except:
            json_response = response.text

        return json_response

    @staticmethod
    @_api_method
    def get_client_credentials_login(login_client_id, login_client_secret, instance_url):
        """
        This function logs into Salesforce using the oAuth 2.0 client
        credentials grant type, so no username or password is needed. The
        calls made with the returned token run as the "Run As" user selected in
        the connected app's client credentials flow settings. In order for
        this function to work, a connected app must be set up in Salesforce
        with "Enable Client Credentials Flow" selected.
        https://help.salesforce.com/s/articleView?id=sf.remoteaccess_oauth_client_credentials_flow.htm

        Args:
            login_client_id (str): this is the client Id from the oAuth settings
                                   in the Salesforce app setup
            login_client_secret (str): this is the secret from the oAuth settings
                                       in the Salesforce app setup
            instance_url (str): The instance url for the org, which is its My
                                Domain url, e.g.
                                https://mycompany.my.salesforce.com. This flow
                                can't be used with login.salesforce.com or
                                test.salesforce.com.

        Returns:
            object: returns the json from the login response body the important
                    aspects of the response are the access_token, which will be
                    used to authenticate the other calls, and instance_url,
                    which is the base endpoint used for the other calls
        """
        if not instance_url.lower().startswith('https://'):
            raise ValueError('The client secret can only be sent to an https URL: {}'.format(instance_url))

        oauth_url = instance_url.rstrip('/') + '/services/oauth2/token'

        login_body_data = {'grant_type': 'client_credentials', 'client_id': login_client_id,
                           'client_secret': login_client_secret}

        response = yield _Request(requestType='POST', URL=oauth_url, data_body=login_body_data, header_details='')
        json_response = json.loads(response.text)

        return json_response

    @staticmethod
    @_api_method
    def get_jwt_bearer_login(login_username, login_client_id, login_client_secret, private_key, is_production):
        """
        This function logs into Salesforce using the oAuth 2.0 JWT bearer
        grant type, so no password is needed. Instead, the request is signed
        with a private key, and the matching certificate is uploaded to the
        connected app in Salesforce ("Use digital signatures"). The user must
        also be pre-authorized for the connected app. After logging in, the
        new token is looked up with introspect_token to find out when it
        expires, which is what the client secret is needed for. This requires
        the PyJWT library, which can be installed with
        `pip install pysalesforceutils[jwt]`.
        https://help.salesforce.com/s/articleView?id=sf.remoteaccess_oauth_jwt_flow.htm

        Args:
            login_username (str): this is the salesforce login of the user to
                                  log in as
            login_client_id (str): this is the client Id from the oAuth settings
                                   in the Salesforce app setup
            login_client_secret (str): this is the secret from the oAuth settings
                                       in the Salesforce app setup
            private_key (str): The contents of the private key file in PEM
                               format. This is the key itself, not the path
                               to the file.
            is_production (bool): this is a boolean value to set whether or not
                                  the base oAuth connection will be in production
                                  or a sandbox environment

        Returns:
            object: returns the json from the login response body the important
                    aspects of the response are the access_token, which will be
                    used to authenticate the other calls, and instance_url,
                    which is the base endpoint used for the other calls. The
                    exp value from introspect_token is added to the response,
                    which is when the token expires in seconds since the epoch.
        """
        if jwt is None:
            raise ImportError(
                "The 'PyJWT' library is required to use the JWT bearer login. "
                "Install it using `pip install pysalesforceutils[jwt]`."
            )

        if is_production:
            base_oauth_url = 'https://login.salesforce.com'
        else:
            base_oauth_url = 'https://test.salesforce.com'

        # Salesforce only accepts requests that expire within 3 minutes
        claims = {'iss': login_client_id, 'sub': login_username, 'aud': base_oauth_url,
                  'exp': int(time.time()) + 180}
        assertion = jwt.encode(claims, private_key, algorithm='RS256')

        login_body_data = {'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer', 'assertion': assertion}

        response = yield _Request(requestType='POST', URL=base_oauth_url + '/services/oauth2/token',
                                  data_body=login_body_data, header_details='')
        json_response = json.loads(response.text)

        introspect_response = yield Authentication.introspect_token._plan(
            json_response['access_token'], login_client_id, login_client_secret, json_response['instance_url'])
        json_response['exp'] = introspect_response['exp']

        return json_response

    @staticmethod
    @_api_method
    def introspect_token(auth_token, login_client_id, login_client_secret, instance_url):
        """
        This function looks up the current state of a token, including whether
        it's still active and when it expires. A connected app can always
        introspect its own tokens. To introspect tokens from other connected
        apps, "Introspect All Tokens" must be selected in the oAuth settings
        of the connected app.
        https://help.salesforce.com/s/articleView?id=sf.remoteaccess_oidc_token_introspection_endpoint.htm

        Args:
            auth_token (str): this is the token received in the access_token
                              response from one of the login functions.
            login_client_id (str): this is the client Id from the oAuth settings
                                   in the Salesforce app setup
            login_client_secret (str): this is the secret from the oAuth settings
                                       in the Salesforce app setup
            instance_url (str): This is the instance_url value received from the
                                login response

        Returns:
            object: returns the json from the introspect response body. The
                    important aspects of the response are active (True or
                    False), and exp, which is when the token expires in
                    seconds since the epoch.
        """
        if not instance_url.lower().startswith('https://'):
            raise ValueError('The access token can only be sent to an https URL: {}'.format(instance_url))

        introspect_url = instance_url.rstrip('/') + '/services/oauth2/introspect'

        introspect_body_data = {'token': auth_token, 'token_type_hint': 'access_token',
                                'client_id': login_client_id, 'client_secret': login_client_secret}

        response = yield _Request(requestType='POST', URL=introspect_url, data_body=introspect_body_data,
                                  header_details='')
        json_response = json.loads(response.text)

        return json_response

    @staticmethod
    @_api_method
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

        response = yield _Request(requestType='POST', URL=logout_url, data_body=logout_body_data, header_details='')

        success = False
        if response.status_code == 200:
            success = True

        json_response = {'success': success, 'status_code': response.status_code}

        return json_response

    @staticmethod
    @_api_method
    def revoke_token(auth_token, instance_url):
        """
        This function logs out by revoking the token at the given url, so it
        doesn't need to know whether the login is production or a sandbox.

        Args:
            auth_token (str): this is the token received in the access_token
                              response from one of the login functions.
            instance_url (str): This is the instance_url value received from the
                                login response
        Returns:
            object: returns a json response with success (True or False), and
                    the status_code returned by the call to revoke the token
        """
        if not instance_url.lower().startswith('https://'):
            raise ValueError('The access token can only be sent to an https URL: {}'.format(instance_url))

        revoke_url = instance_url.rstrip('/') + '/services/oauth2/revoke'

        response = yield _Request(requestType='POST', URL=revoke_url, data_body={'token': auth_token},
                                  header_details='')

        json_response = {'success': response.status_code == 200, 'status_code': response.status_code}

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
