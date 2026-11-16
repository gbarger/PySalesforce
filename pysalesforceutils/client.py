#!/usr/bin/python3

"""
A client that remembers the access token and instance url, so they don't need
to be passed to every method.
"""

import functools
import inspect

import httpx

from .authentication import Authentication
from .bulk import Bulk
from .bulk2 import Bulk2
from .standard import Standard
from .tooling import Tooling
from .util import _run_async

_CLIENT_ARGUMENTS = ('access_token', 'instance_url')


def _bind(method, client):
    """
    Wraps one of the static API methods so that the access_token and
    instance_url arguments are filled in from the client when it's called.
    """
    signature = inspect.signature(method)
    bound_signature = signature.replace(
        parameters=[parameter for name, parameter in signature.parameters.items() if name not in _CLIENT_ARGUMENTS])

    @functools.wraps(method)
    def bound_method(*args, **kwargs):
        arguments = bound_signature.bind(*args, **kwargs).arguments

        return method(access_token=client.access_token, instance_url=client.instance_url, **arguments)

    bound_method.__signature__ = bound_signature

    return bound_method


def _bind_async(method, client):
    """
    The async version of _bind. The method's plan is run with the client's
    httpx.AsyncClient, so the bound method is a coroutine function.
    """
    signature = inspect.signature(method)
    bound_signature = signature.replace(
        parameters=[parameter for name, parameter in signature.parameters.items() if name not in _CLIENT_ARGUMENTS])

    @functools.wraps(method)
    async def bound_method(*args, **kwargs):
        arguments = bound_signature.bind(*args, **kwargs).arguments
        plan = method._plan(access_token=client.access_token, instance_url=client.instance_url, **arguments)

        return await _run_async(plan, client.http_client)

    bound_method.__signature__ = bound_signature

    return bound_method


class _BoundApi:
    """
    Has the same methods as one of the API classes (Standard, Tooling, Bulk or
    Bulk2), but without the access_token and instance_url arguments.
    """

    def __init__(self, api_class, client, bind=_bind):
        for name, attribute in vars(api_class).items():
            if isinstance(attribute, staticmethod) and not name.startswith('_'):
                setattr(self, name, bind(attribute.__func__, client))


class Salesforce:
    """
    Calls the Salesforce APIs for one login. The methods are the same as the
    ones on the Standard, Tooling, Bulk and Bulk2 classes, but the
    access_token and instance_url arguments are left out. For example:

        sf = Salesforce(access_token, instance_url)

        sf.standard.query('SELECT Id FROM Account')
        sf.tooling.execute_anonymous(code_string)
        sf.bulk.update_sobject_rows('Account', records, 1000, 5)
        sf.bulk2.get_job_info(job_id)

    Args:
        access_token (str): This is the access_token value received from the
                            login response
        instance_url (str): This is the instance_url value received from the
                            login response
    """

    def __init__(self, access_token, instance_url):
        self.access_token = access_token
        self.instance_url = instance_url
        self.token_expiration = None

        self.standard = _BoundApi(Standard, self)
        self.tooling = _BoundApi(Tooling, self)
        self.bulk = _BoundApi(Bulk, self)
        self.bulk2 = _BoundApi(Bulk2, self)

    @classmethod
    def login(cls, login_username, login_password, login_client_id, login_client_secret, is_production=True):
        """
        Logs into Salesforce with Authentication.get_oauth_login and returns a
        client for that login.

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
                                  or a sandbox environment. Defaults to True

        Returns:
            Salesforce: Returns a client for the new login.
        """
        login_response = Authentication.get_oauth_login(login_username, login_password, login_client_id,
                                                        login_client_secret, is_production)

        return cls(login_response['access_token'], login_response['instance_url'])

    @classmethod
    def login_client_credentials(cls, login_client_id, login_client_secret, instance_url):
        """
        Logs into Salesforce with Authentication.get_client_credentials_login
        and returns a client for that login.

        Args:
            login_client_id (str): this is the client Id from the oAuth settings
                                   in the Salesforce app setup
            login_client_secret (str): this is the secret from the oAuth settings
                                       in the Salesforce app setup
            instance_url (str): The instance url for the org, which is its My
                                Domain url, e.g.
                                https://mycompany.my.salesforce.com

        Returns:
            Salesforce: Returns a client for the new login.
        """
        login_response = Authentication.get_client_credentials_login(login_client_id, login_client_secret,
                                                                     instance_url)

        return cls(login_response['access_token'], login_response['instance_url'])

    @classmethod
    def login_jwt_bearer(cls, login_username, login_client_id, login_client_secret, private_key, is_production=True):
        """
        Logs into Salesforce with Authentication.get_jwt_bearer_login and
        returns a client for that login. The token_expiration value on the
        client is when the token expires in seconds since the epoch.

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
                                  or a sandbox environment. Defaults to True

        Returns:
            Salesforce: Returns a client for the new login.
        """
        login_response = Authentication.get_jwt_bearer_login(login_username, login_client_id, login_client_secret,
                                                             private_key, is_production)

        client = cls(login_response['access_token'], login_response['instance_url'])
        client.token_expiration = login_response['exp']

        return client

    def logout(self):
        """
        Revokes the access token with Authentication.revoke_token.

        Returns:
            object: returns a json response with success (True or False), and
                    the status_code returned by the call to revoke the token
        """
        return Authentication.revoke_token(self.access_token, self.instance_url)


class AsyncSalesforce:
    """
    The async version of the Salesforce client. It has the same standard,
    tooling, bulk and bulk2 methods, but each one is a coroutine that has to
    be awaited, and polling waits use asyncio.sleep so other tasks keep
    running. The Metadata API is not included because it's SOAP, which is
    only available synchronously.

    The client sends its requests with its own httpx.AsyncClient, so close it
    when you're done, either with async with or by awaiting aclose(). For
    example:

        async with await AsyncSalesforce.login(username, password, client_id, client_secret) as sf:
            accounts = await sf.standard.query('SELECT Id FROM Account')

    Args:
        access_token (str): This is the access_token value received from the
                            login response
        instance_url (str): This is the instance_url value received from the
                            login response
    """

    def __init__(self, access_token, instance_url):
        self.access_token = access_token
        self.instance_url = instance_url
        self.token_expiration = None

        # the client's own connection pool. Replace it before making any
        # calls if you need different httpx settings, e.g. a proxy
        self.http_client = httpx.AsyncClient(follow_redirects=True)

        self.standard = _BoundApi(Standard, self, _bind_async)
        self.tooling = _BoundApi(Tooling, self, _bind_async)
        self.bulk = _BoundApi(Bulk, self, _bind_async)
        self.bulk2 = _BoundApi(Bulk2, self, _bind_async)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        await self.aclose()

    async def aclose(self):
        """
        Closes the client's connections. This does not log out.
        """
        await self.http_client.aclose()

    async def _login(self, plan):
        """
        Runs a login plan with this client's connections, and keeps the
        access token and instance url from the response.
        """
        try:
            login_response = await _run_async(plan, self.http_client)
        except BaseException:
            await self.aclose()
            raise

        self.access_token = login_response['access_token']
        self.instance_url = login_response['instance_url']

        return login_response

    @classmethod
    async def login(cls, login_username, login_password, login_client_id, login_client_secret, is_production=True):
        """
        Logs into Salesforce like Authentication.get_oauth_login and returns
        a client for that login.

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
                                  or a sandbox environment. Defaults to True

        Returns:
            AsyncSalesforce: Returns a client for the new login.
        """
        client = cls(None, None)
        await client._login(Authentication.get_oauth_login._plan(login_username, login_password, login_client_id,
                                                                 login_client_secret, is_production))

        return client

    @classmethod
    async def login_client_credentials(cls, login_client_id, login_client_secret, instance_url):
        """
        Logs into Salesforce like Authentication.get_client_credentials_login
        and returns a client for that login.

        Args:
            login_client_id (str): this is the client Id from the oAuth settings
                                   in the Salesforce app setup
            login_client_secret (str): this is the secret from the oAuth settings
                                       in the Salesforce app setup
            instance_url (str): The instance url for the org, which is its My
                                Domain url, e.g.
                                https://mycompany.my.salesforce.com

        Returns:
            AsyncSalesforce: Returns a client for the new login.
        """
        client = cls(None, None)
        await client._login(Authentication.get_client_credentials_login._plan(login_client_id, login_client_secret,
                                                                              instance_url))

        return client

    @classmethod
    async def login_jwt_bearer(cls, login_username, login_client_id, login_client_secret, private_key,
                               is_production=True):
        """
        Logs into Salesforce like Authentication.get_jwt_bearer_login and
        returns a client for that login. The token_expiration value on the
        client is when the token expires in seconds since the epoch.

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
                                  or a sandbox environment. Defaults to True

        Returns:
            AsyncSalesforce: Returns a client for the new login.
        """
        client = cls(None, None)
        login_response = await client._login(Authentication.get_jwt_bearer_login._plan(
            login_username, login_client_id, login_client_secret, private_key, is_production))
        client.token_expiration = login_response['exp']

        return client

    async def logout(self):
        """
        Revokes the access token like Authentication.revoke_token. This does
        not close the client's connections.

        Returns:
            object: returns a json response with success (True or False), and
                    the status_code returned by the call to revoke the token
        """
        return await _run_async(Authentication.revoke_token._plan(self.access_token, self.instance_url),
                                self.http_client)
