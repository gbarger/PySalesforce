# Configuration and errors

[Back to the README](../README.md)

- [API version](#api-version)
- [Timeout](#timeout)
- [Connections](#connections)
- [Errors](#errors)
- [Safe values in urls and queries](#safe-values-in-urls-and-queries)
- [Optional libraries](#optional-libraries)
- [Util helpers](#util-helpers)

## API version

The REST, Bulk and Tooling calls use the Salesforce API version in `pysalesforceutils.API_VERSION`. To use a different version, set it before making your calls:

```python
import pysalesforceutils

pysalesforceutils.API_VERSION = '60.0'
```

The setting applies to the whole program, including every `Salesforce` client. It doesn't affect the Metadata API, which uses the version of its [WSDL files](metadata.md#wsdl-files).

## Timeout

By default, a request fails if Salesforce doesn't connect or send any data for 120 seconds. To change it:

```python
from pysalesforceutils import webservice

webservice.Tools.default_timeout = 30      # seconds
webservice.Tools.default_timeout = None    # wait forever
```

When the time runs out, the library raises `requests.exceptions.Timeout`. The timeout is the wait for the next piece of data, not the total time for the request, so a large download that keeps sending data isn't cut off.

## Connections

All requests share one `requests.Session`, so connections to Salesforce are reused instead of being opened again for every call. The session is available as `webservice.Tools.session` if you need to change it, for example to use a proxy or to retry failed connections:

```python
from requests.adapters import HTTPAdapter
from pysalesforceutils import webservice

webservice.Tools.session.proxies = {'https': 'http://proxy.example.com:8080'}
webservice.Tools.session.mount('https://', HTTPAdapter(max_retries=3))
```

The library only sends a token to an `https` url. A call with an `http` instance url raises `ValueError` before anything is sent.

## Errors

| Exception | When it's raised |
|---|---|
| `requests.exceptions.HTTPError` | Salesforce answered with an error status, such as 400 or 404 |
| `requests.exceptions.Timeout` | Salesforce didn't answer in time |
| `requests.exceptions.ConnectionError` | The connection to Salesforce failed |
| `ValueError` | An argument can't be used, such as an `http` url, or `.` or `..` as a record Id |
| `ImportError` | The method needs an optional library that isn't installed |

The `HTTPError` message includes the body of the response, and the response is on the exception:

```python
import requests
from pysalesforceutils import Standard

try:
    Standard.get_sobject_row('Account', record_id, 'Id,Name', access_token, instance_url)
except requests.exceptions.HTTPError as error:
    if error.response.status_code == 404:
        print('The record does not exist')
    elif error.response.status_code == 401:
        print('The token has expired, log in again')
    else:
        print(error.response.json())
```

The HTTP status only tells you about the request as a whole. Requests that work on several records, such as `create_sobject_rows`, the composite requests and the Bulk jobs, succeed with a status of 200 even when some of the records fail. Check the result for each record.

## Safe values in urls and queries

Object names, record Ids, job Ids and field lists are url encoded before they're added to a request, so a value can't change which resource is called. You don't need to encode them yourself.

There are two things the library can't do for you:

- **Query strings.** The library sends your SOQL or SOSL as it is. When part of a query comes from a user or another system, quote it with `Util.soql_quote`:

  ```python
  from pysalesforceutils import Util

  query = 'SELECT Id FROM Contact WHERE LastName = ' + Util.soql_quote(last_name)
  ```

  `soql_quote` wraps the value in single quotes and escapes the characters that could end the string early. It doesn't escape the `LIKE` wildcards `%` and `_`.

- **Paths you write yourself.** `Standard.request` and `Standard.apex_rest_request` use the path exactly as you give it. Encode any value that didn't come from your own code with `urllib.parse.quote(value, safe='')`.

## Optional libraries

| Library | Needed for | Install with |
|---|---|---|
| `zeep` | The `Metadata` class and `Authentication.get_soap_login` | `pip install pysalesforceutils[soap]` |
| `PyJWT` | `Authentication.get_jwt_bearer_login` and `Salesforce.login_jwt_bearer` | `pip install pysalesforceutils[jwt]` |

Everything else works without them. If you call one of these methods without the library installed, it raises an `ImportError` that tells you what to install.

## Util helpers

| Method | What it does |
|---|---|
| `Util.soql_quote(value)` | Quotes a string for use in a SOQL or SOSL query |
| `Util.chunk(list, n)` | Splits a list into lists of `n` items |
| `Util.get_standard_header(access_token)` | Returns the headers used for REST calls |
| `Util.get_bulk_header(access_token)` | Returns the headers used for Bulk API calls |

The `webservice.Tools` class has the methods the library uses to send requests: `get_http_response`, `post_http_response`, `put_http_response`, `patch_http_response` and `delete_http_response`. You can use them to call any url with your own headers.
