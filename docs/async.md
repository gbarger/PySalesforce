# Async

[Back to the README](../README.md)

- [The AsyncSalesforce client](#the-asyncsalesforce-client)
- [Logging in](#logging-in)
- [Closing the client](#closing-the-client)
- [Running calls at the same time](#running-calls-at-the-same-time)
- [Waiting for Bulk jobs](#waiting-for-bulk-jobs)
- [Connections](#connections)
- [What isn't async](#what-isnt-async)

## The AsyncSalesforce client

`AsyncSalesforce` is the `asyncio` version of the [`Salesforce` client](authentication.md#the-salesforce-client). It has the same `standard`, `tooling`, `bulk` and `bulk2` methods, with the same arguments and results, but each one is a coroutine that you `await`. While a call waits for Salesforce, the event loop keeps running your other tasks.

```python
import asyncio
from pysalesforceutils import AsyncSalesforce

async def main():
    async with AsyncSalesforce(access_token, instance_url) as sf:
        accounts = await sf.standard.query_records('SELECT Id, Name FROM Account LIMIT 10')
        await sf.standard.update_sobject_row('Account', record_id, {'Phone': '(123) 456-7890'}, False)

asyncio.run(main())
```

Because the methods are the same, the documentation for the static classes and the `Salesforce` client also describes the async ones. `help(sf.standard.query)` shows the same docstring.

The client has the same `access_token`, `instance_url` and `token_expiration` attributes as `Salesforce`, plus `http_client`, the `httpx.AsyncClient` it sends its requests with.

## Logging in

Each login is an async class method that returns a client:

```python
sf = await AsyncSalesforce.login_client_credentials(client_id, client_secret, 'https://mycompany.my.salesforce.com')
sf = await AsyncSalesforce.login_jwt_bearer('user@example.com', client_id, client_secret, private_key, is_production=True)
sf = await AsyncSalesforce.login(username, password_and_security_token, client_id, client_secret, is_production=True)
```

They take the same arguments as the `Salesforce` logins, and need the same [connected app settings](authentication.md#connected-app). `await sf.logout()` revokes the token.

## Closing the client

Each `AsyncSalesforce` keeps its own connections open, so close it when you're done. The simplest way is `async with`, which closes it at the end of the block:

```python
async with await AsyncSalesforce.login(username, password, client_id, client_secret) as sf:
    ...
```

Or close it yourself:

```python
sf = await AsyncSalesforce.login(username, password, client_id, client_secret)
try:
    ...
finally:
    await sf.aclose()
```

Closing the client doesn't log out, and logging out doesn't close the client. If a login fails, the client it created is closed for you.

## Running calls at the same time

Use `asyncio.gather` (or a `TaskGroup`) to run several calls at once:

```python
accounts, contacts, limits = await asyncio.gather(
    sf.standard.query_records('SELECT Id, Name FROM Account'),
    sf.standard.query_records('SELECT Id, Name FROM Contact'),
    sf.standard.get_limits(),
)
```

Salesforce limits how many long-running requests an org can have at once, and every call counts toward the daily API request limit, so don't start thousands of calls together. An `asyncio.Semaphore` is an easy way to cap how many run at a time. For large numbers of records, the [Bulk APIs](bulk.md) or [composite requests](composite.md) use far fewer calls.

## Waiting for Bulk jobs

The Bulk methods that wait for a job, such as `bulk2.get_job_status` and `bulk.insert_sobject_rows`, wait with `asyncio.sleep`, so other tasks keep running while a job is processing.

## Connections

The client's `httpx.AsyncClient` is in `sf.http_client`. To use different `httpx` settings, such as a proxy, close it and replace it before making any calls. Keep `follow_redirects=True`:

```python
import httpx

sf = AsyncSalesforce(access_token, instance_url)
await sf.http_client.aclose()
sf.http_client = httpx.AsyncClient(follow_redirects=True, proxy='http://proxy.example.com:8080')
```

The timeout is the same `webservice.Tools.default_timeout` setting the synchronous calls use. See [Configuration and errors](configuration.md#timeout). Errors are the same too: an error status raises `httpx.HTTPStatusError`.

## What isn't async

- **The Metadata API** and **the SOAP login** use SOAP through `zeep`, which is synchronous. If you call them from async code, run them in a thread so they don't block the event loop:

  ```python
  result = await asyncio.to_thread(Metadata.list_metadata, query, api_version, session_id, metadata_url, client_name)
  ```

- **The static classes** (`Standard`, `Bulk` and so on) and the `Salesforce` client are always synchronous.
- **The `Composite` builders** don't make any requests, so they're used the same way with both clients.
