# Authentication

[Back to the README](../README.md)

Every API call needs an access token and the instance url of your org. This page covers how to get them, how to find out when a token expires, and how to log out.

- [Connected app](#connected-app)
- [Choosing a login](#choosing-a-login)
- [Client credentials login](#client-credentials-login)
- [JWT bearer login](#jwt-bearer-login)
- [Username and password login](#username-and-password-login)
- [The Salesforce client](#the-salesforce-client)
- [Token expiration](#token-expiration)
- [Logging out](#logging-out)
- [SOAP login](#soap-login)

## Connected app

All of the OAuth logins need a connected app in Salesforce. After you create it, Salesforce gives you a Consumer Key and a Consumer Secret. These are the `login_client_id` and `login_client_secret` arguments in this library.

Only grant the OAuth scopes you need. "Manage user data via APIs (api)" is enough for the methods in this library, so avoid Full Access.

## Choosing a login

| Login | Stores a password? | Connected app setting it needs | Extra install |
|---|---|---|---|
| Client credentials | No | "Enable Client Credentials Flow" and a "Run As" user | None |
| JWT bearer | No | "Use digital signatures" with your certificate, and the user pre-authorized | `pysalesforceutils[jwt]` |
| Username and password | Yes | None | None |

Client credentials is the simplest choice for a server that always acts as the same user. JWT bearer lets you choose the user to log in as. The username and password login is the oldest: Salesforce recommends the other flows and may not allow it in newer orgs.

Each login returns the response from Salesforce as a dict. The two values you need are `access_token` and `instance_url`.

## Client credentials login

```python
from pysalesforceutils import Authentication

login = Authentication.get_client_credentials_login(client_id, client_secret, 'https://mycompany.my.salesforce.com')

access_token = login['access_token']
instance_url = login['instance_url']
```

The `instance_url` argument is the My Domain url of your org. This login can't be sent to `login.salesforce.com` or `test.salesforce.com`. The calls made with the token run as the "Run As" user selected in the connected app.

## JWT bearer login

```python
from pysalesforceutils import Authentication

with open('server.key') as key_file:
    private_key = key_file.read()

login = Authentication.get_jwt_bearer_login('user@example.com', client_id, client_secret, private_key, True)

access_token = login['access_token']
instance_url = login['instance_url']
expires = login['exp']
```

- `private_key` is the contents of the private key file in PEM format, not the path to the file. The matching certificate is uploaded to the connected app.
- The last argument is `is_production`. Use `True` for production and `False` for a sandbox.
- After logging in, this method looks up the new token with `introspect_token`, which is what the client secret is for. The `exp` value it adds to the response is when the token expires, in seconds since the epoch.

## Username and password login

```python
from pysalesforceutils import Authentication

login = Authentication.get_oauth_login(username, password_and_security_token, client_id, client_secret, True)

access_token = login['access_token']
instance_url = login['instance_url']
```

The password argument is the user's password followed by their security token. The last argument is `is_production`.

## The Salesforce client

The `Salesforce` class has a method for each login that returns a client for the new session.

```python
from pysalesforceutils import Salesforce

sf = Salesforce.login_client_credentials(client_id, client_secret, 'https://mycompany.my.salesforce.com')
sf = Salesforce.login_jwt_bearer('user@example.com', client_id, client_secret, private_key, is_production=True)
sf = Salesforce.login(username, password_and_security_token, client_id, client_secret, is_production=True)

sf = Salesforce(access_token, instance_url)    # if you already have a token
```

The client has these attributes:

| Attribute | What it is |
|---|---|
| `sf.standard`, `sf.tooling`, `sf.bulk`, `sf.bulk2` | The methods of the `Standard`, `Tooling`, `Bulk` and `Bulk2` classes, without the `access_token` and `instance_url` arguments |
| `sf.access_token` | The token used for each call. Set it to a new token and the next call uses it. |
| `sf.instance_url` | The instance url used for each call |
| `sf.token_expiration` | When the token expires, in seconds since the epoch. Only set by `login_jwt_bearer`, otherwise `None`. |

The `Metadata` and `Composite` classes are not on the client. `Metadata` uses a SOAP session, and the `Composite` builders don't need a token.

For `asyncio` code, `AsyncSalesforce` has the same logins and methods as coroutines. See [Async](async.md).

## Token expiration

Salesforce doesn't include an expiration in the login response. To find out when a token expires, look it up with the introspect service:

```python
from pysalesforceutils import Authentication

token_info = Authentication.introspect_token(access_token, client_id, client_secret, instance_url)

print(token_info['active'])    # True if the token can still be used
print(token_info['exp'])       # when it expires, in seconds since the epoch
```

A connected app can always introspect its own tokens. The "Introspect All Tokens" setting on a connected app is only needed if that app should also be able to look up tokens that were issued to other connected apps. It doesn't change what the login returns.

## Logging out

```python
from pysalesforceutils import Authentication

result = Authentication.revoke_token(access_token, instance_url)
print(result)    # {'success': True, 'status_code': 200}
```

With the client, call `sf.logout()`, which does the same thing.

`Authentication.get_oauth_logout(auth_token, is_production)` is the older method. It revokes the token at `login.salesforce.com` or `test.salesforce.com` and returns the same result.

## SOAP login

The Metadata API uses a SOAP session instead of an OAuth token. This needs `pip install pysalesforceutils[soap]`.

```python
from pysalesforceutils import Authentication

login_result = Authentication.get_soap_login(username, password_and_security_token, None, None, None, None, True)

session_id = login_result['sessionId']
metadata_url = login_result['metadataServerUrl']
```

The four `None` arguments are `org_id`, `portal_id`, `client_name` and `default_ns`, which are only needed for self-service users and partner applications. The last argument is `is_production`. See [Metadata API](metadata.md) for how the session is used.
