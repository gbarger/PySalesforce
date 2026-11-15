# PySalesforce

`pysalesforceutils` is a Python library that wraps the Salesforce APIs: the REST API (including composite requests), Bulk API, Bulk API 2.0, Tooling API and Metadata API.

This is an independent open source project. It is not produced or supported by Salesforce.

## Contents

- [Installation](#installation)
- [Quick start](#quick-start)
- [Logging in](#logging-in)
- [What's included](#whats-included)
- [Configuration](#configuration)
- [Errors](#errors)
- [Documentation](#documentation)
- [Running the tests](#running-the-tests)
- [License](#license)

## Installation

```
pip install pysalesforceutils
```

The only required dependency is `requests`. Two features need an extra library, which is only installed if you ask for it:

| Feature | Install with | Library |
|---|---|---|
| Metadata API and SOAP login | `pip install pysalesforceutils[soap]` | `zeep` |
| JWT bearer login | `pip install pysalesforceutils[jwt]` | `PyJWT` |

## Quick start

There are two ways to call the library. Both make the same requests.

### With the `Salesforce` client

The client remembers the access token and instance url, so you don't pass them to every method.

```python
from pysalesforceutils import Salesforce

sf = Salesforce.login_client_credentials(client_id, client_secret, 'https://mycompany.my.salesforce.com')

accounts = sf.standard.query_records('SELECT Id, Name FROM Account LIMIT 10')
result = sf.standard.create_sobject_row('Account', {'Name': 'Cloudy Consulting'}, False)
sf.standard.update_sobject_row('Account', record_id, {'Phone': '(123) 456-7890'}, False)

sf.logout()
```

The methods are grouped by API: `sf.standard`, `sf.tooling`, `sf.bulk` and `sf.bulk2`. If you already have a token, create the client directly with `Salesforce(access_token, instance_url)`.

### With the static classes

Every method is also available as a static method that takes `access_token` and `instance_url`.

```python
from pysalesforceutils import Authentication, Standard

login = Authentication.get_client_credentials_login(client_id, client_secret, 'https://mycompany.my.salesforce.com')
access_token = login['access_token']
instance_url = login['instance_url']

accounts = Standard.query_records('SELECT Id, Name FROM Account LIMIT 10', access_token, instance_url)
```

The client has exactly the same methods with the last two arguments left out, so the documentation for a static method also describes the client method.

## Logging in

All of the logins need a connected app in Salesforce, which provides the Consumer Key (client id) and Consumer Secret (client secret). Only grant the OAuth scopes you need: "Manage user data via APIs (api)" is enough for the methods in this library, so avoid Full Access.

| Login | Client method | Needs |
|---|---|---|
| Client credentials | `Salesforce.login_client_credentials` | Client id, client secret, instance url |
| JWT bearer | `Salesforce.login_jwt_bearer` | Username, client id, client secret, private key |
| Username and password | `Salesforce.login` | Username, password + security token, client id, client secret |

See [Authentication](https://github.com/gbarger/PySalesforce/blob/master/docs/authentication.md) for the connected app settings each login needs, the matching `Authentication` methods, token expiration and logging out.

## What's included

| Class | What it covers | Documentation |
|---|---|---|
| `Salesforce` | A client that holds the token for one login | [Authentication](https://github.com/gbarger/PySalesforce/blob/master/docs/authentication.md) |
| `Authentication` | Logging in and out, token introspection | [Authentication](https://github.com/gbarger/PySalesforce/blob/master/docs/authentication.md) |
| `Standard` | REST API: records, queries, search, describe, limits, actions, Apex REST | [Standard REST API](https://github.com/gbarger/PySalesforce/blob/master/docs/standard.md) |
| `Composite` | Builders for composite, batch and graph requests | [Composite requests](https://github.com/gbarger/PySalesforce/blob/master/docs/composite.md) |
| `Bulk` and `Bulk2` | Bulk API and Bulk API 2.0 for large data sets | [Bulk APIs](https://github.com/gbarger/PySalesforce/blob/master/docs/bulk.md) |
| `Tooling` | Tooling API: anonymous Apex, Apex tests, Tooling records | [Tooling API](https://github.com/gbarger/PySalesforce/blob/master/docs/tooling.md) |
| `Metadata` | Metadata API: retrieve, deploy and manage metadata | [Metadata API](https://github.com/gbarger/PySalesforce/blob/master/docs/metadata.md) |
| `Util` | Helpers, including `Util.soql_quote` for safe query values | [Configuration and errors](https://github.com/gbarger/PySalesforce/blob/master/docs/configuration.md) |

Every method also has a docstring that describes its arguments and what it returns, so `help(Standard.query)` works in a Python shell.

## Configuration

```python
import pysalesforceutils
from pysalesforceutils import webservice

pysalesforceutils.API_VERSION = '60.0'       # the Salesforce API version used for REST calls
webservice.Tools.default_timeout = 30        # seconds to wait for Salesforce, None to wait forever
```

See [Configuration and errors](https://github.com/gbarger/PySalesforce/blob/master/docs/configuration.md) for the defaults and the other settings.

## Errors

When Salesforce answers with an error status, the library raises `requests.exceptions.HTTPError`. The message includes the response body, and the response itself is available on the exception.

```python
import requests

try:
    sf.standard.get_sobject_row('Account', record_id, 'Id,Name')
except requests.exceptions.HTTPError as error:
    print(error.response.status_code)
    print(error.response.text)
```

## Documentation

- [Authentication](https://github.com/gbarger/PySalesforce/blob/master/docs/authentication.md)
- [Standard REST API](https://github.com/gbarger/PySalesforce/blob/master/docs/standard.md)
- [Composite requests](https://github.com/gbarger/PySalesforce/blob/master/docs/composite.md)
- [Bulk APIs](https://github.com/gbarger/PySalesforce/blob/master/docs/bulk.md)
- [Tooling API](https://github.com/gbarger/PySalesforce/blob/master/docs/tooling.md)
- [Metadata API](https://github.com/gbarger/PySalesforce/blob/master/docs/metadata.md)
- [Configuration and errors](https://github.com/gbarger/PySalesforce/blob/master/docs/configuration.md)

Salesforce's own reference for each API:

- [REST API](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/intro_what_is_rest_api.htm)
- [Bulk API](https://developer.salesforce.com/docs/atlas.en-us.api_asynch.meta/api_asynch/asynch_api_intro.htm)
- [Bulk API 2.0](https://developer.salesforce.com/docs/atlas.en-us.api_bulk_v2.meta/api_bulk_v2/introduction_bulk_api_2.htm)
- [Tooling API](https://developer.salesforce.com/docs/atlas.en-us.api_tooling.meta/api_tooling/intro_rest_resources.htm)
- [Metadata API](https://developer.salesforce.com/docs/atlas.en-us.api_meta.meta/api_meta/meta_intro.htm)

## Running the tests

The tests use `unittest` from the standard library and don't call Salesforce: the HTTP requests are replaced with mocks, and the tests check the requests the library would send.

```
python -m unittest discover -s test -t .
```

## License

GNU General Public License v3. See [LICENSE](https://github.com/gbarger/PySalesforce/blob/master/LICENSE).
