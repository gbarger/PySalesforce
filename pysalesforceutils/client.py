#!/usr/bin/python3

"""
A client that remembers the access token and instance url, so they don't need
to be passed to every method.
"""

import functools
import inspect

from .authentication import Authentication
from .bulk import Bulk
from .bulk2 import Bulk2
from .standard import Standard
from .tooling import Tooling

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


class _BoundApi:
    """
    Has the same methods as one of the API classes (Standard, Tooling, Bulk or
    Bulk2), but without the access_token and instance_url arguments.
    """

    def __init__(self, api_class, client):
        for name, attribute in vars(api_class).items():
            if isinstance(attribute, staticmethod) and not name.startswith('_'):
                setattr(self, name, _bind(attribute.__func__, client))


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
        is_production (bool): Whether this login is for production or a
                              sandbox environment. This is only used by
                              logout. Defaults to True
    """

    def __init__(self, access_token, instance_url, is_production=True):
        self.access_token = access_token
        self.instance_url = instance_url
        self.is_production = is_production

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

        return cls(login_response['access_token'], login_response['instance_url'], is_production)

    def logout(self):
        """
        Revokes the access token with Authentication.get_oauth_logout.

        Returns:
            object: returns a json response with success (True or False), and
                    the status_code returned by the call to revoke the token
        """
        return Authentication.get_oauth_logout(self.access_token, self.is_production)
