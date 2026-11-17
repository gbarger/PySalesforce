# Metadata API

[Back to the README](../README.md)

The `Metadata` class wraps the Salesforce Metadata API, which retrieves, deploys and changes the customizations in an org, such as custom objects, page layouts and Apex classes.

- [Before you start](#before-you-start)
- [Retrieving metadata](#retrieving-metadata)
- [Deploying metadata](#deploying-metadata)
- [Reading and changing components](#reading-and-changing-components)
- [Listing and describing metadata](#listing-and-describing-metadata)
- [WSDL files](#wsdl-files)

## Before you start

The Metadata API is a SOAP API, so it works differently from the rest of the library:

- It needs the `zeep` library: `pip install pysalesforceutils[soap]`.
- It uses a session Id and a metadata url instead of an access token and instance url. Both come from the [SOAP login](authentication.md#soap-login).
- It isn't part of the `Salesforce` client. Call the methods on the `Metadata` class.

```python
from pysalesforceutils import Authentication

login_result = Authentication.get_soap_login(username, password_and_security_token, None, None, None, None, True)

session_id = login_result['sessionId']
metadata_url = login_result['metadataServerUrl']
```

Most methods take a `client_name` argument, which identifies a partner application. Use `None` unless you have one.

## Retrieving metadata

Retrieving is asynchronous. You start the retrieve, then check its status until it's done.

```python
import time
from pysalesforceutils import Metadata

members = Metadata.get_package_type_members('ApexClass', ['*'])
package = Metadata.get_package(version='68.0', types=[members])
retrieve_request = Metadata.get_retrieve_request(api_version=68.0, single_package=True, unpackaged=package)

async_result = Metadata.retrieve(retrieve_request, session_id, metadata_url, None)

while True:
    status = Metadata.check_retrieve_status(async_result['id'], True, session_id, metadata_url, None)

    if status['done']:
        break

    time.sleep(5)

with open('retrieved.zip', 'wb') as zip_file:
    zip_file.write(status['zipFile'])
```

| Method | What it does |
|---|---|
| `get_package_type_members(member_name, member_list)` | Lists the components of one metadata type. `['*']` means all of them. |
| `get_package(**kwargs)` | Builds the package to retrieve. `version` is required, and `types` is the list of type members. |
| `get_retrieve_request(**kwargs)` | Builds the retrieve request. `api_version` is required. |
| `retrieve(retrieve_request, session_id, metadata_url, client_name)` | Starts the retrieve |
| `check_retrieve_status(async_process_id, include_zip, session_id, metadata_url, client_name)` | Returns the status, and the zip file when `include_zip` is `True` |

## Deploying metadata

```python
import time
from pysalesforceutils import Metadata

with open('deploy.zip', 'rb') as zip_file:
    zip_data = zip_file.read()

deploy_options = Metadata.get_deploy_options(check_only=True, rollback_on_error=True, single_package=True,
                                             test_level='RunLocalTests')

async_result = Metadata.deploy(zip_data, deploy_options, session_id, metadata_url, None, None)

while True:
    status = Metadata.check_deploy_status(async_result['id'], True, session_id, metadata_url, None)

    if status['done']:
        break

    time.sleep(5)

print(status['status'], status['numberComponentErrors'])
```

| Method | What it does |
|---|---|
| `get_deploy_options(**kwargs)` | Builds the options, such as `check_only`, `rollback_on_error`, `run_tests` and `test_level` |
| `deploy(zip_file, deploy_options, session_id, metadata_url, client_name, debug_categories)` | Starts the deployment |
| `check_deploy_status(deploy_id, include_details, session_id, metadata_url, client_name)` | Returns the status of the deployment |
| `cancel_deploy(deploy_id, session_id, metadata_url, client_name)` | Cancels a deployment |
| `deploy_recent_validation(validation_id, session_id, metadata_url, client_name, debug_categories)` | Deploys a validation that already passed, without running the tests again |

Set `check_only` to `True` to validate a deployment without saving anything. `rollback_on_error` must be `True` for a production org. The docstring for `get_deploy_options` describes every option.

## Reading and changing components

These methods work on a few components at a time and finish straight away. Salesforce limits most of them to 10 components per call.

| Method | What it does |
|---|---|
| `read_metadata(metadata_type, full_names, session_id, metadata_url, client_name)` | Returns the components with the given names |
| `create_metadata(metadata_list, session_id, metadata_url, client_name, all_or_none)` | Creates components |
| `update_metadata(metadata_list, session_id, metadata_url, client_name, all_or_none)` | Updates components |
| `upsert_metadata(metadata_list, session_id, metadata_url, client_name, all_or_none)` | Creates or updates components |
| `delete_metadata(metadata_type, full_names, session_id, metadata_url, client_name, all_or_none)` | Deletes components |
| `rename_metadata(metadata_type, old_full_name, new_full_name, session_id, metadata_url, client_name)` | Renames a component |

```python
from pysalesforceutils import Metadata

result = Metadata.read_metadata('CustomObject', ['Account', 'Invoice__c'], session_id, metadata_url, None)
```

## Listing and describing metadata

| Method | What it does |
|---|---|
| `describe_metadata(as_of_version, session_id, metadata_url, client_name)` | Lists the metadata types the org supports |
| `describe_value_type(value_type, session_id, metadata_url)` | Describes the fields of a metadata type |
| `get_list_metadata_query(folder, metadata_type)` | Builds a query for `list_metadata` |
| `list_metadata(list_metadata_query, as_of_version, session_id, metadata_url, client_name)` | Lists the components of a metadata type |

```python
from pysalesforceutils import Metadata

query = Metadata.get_list_metadata_query(None, 'CustomObject')
components = Metadata.list_metadata([query], 68.0, session_id, metadata_url, None)

for component in components:
    print(component['fullName'])
```

## WSDL files

The SOAP calls are built from WSDL files that are included with the library. They are for API version 68.0, so metadata types that Salesforce added after that version aren't available through these methods. The `API_VERSION` setting doesn't affect them.

To use a newer version, download the Metadata WSDL and Partner WSDL from Setup in your org and point the library at your files before making any calls:

```python
import pysalesforceutils

pysalesforceutils.METADATA_WSDL_FILE = '/path/to/metadata.wsdl'
pysalesforceutils.PARTNER_WSDL_FILE = '/path/to/partner.wsdl'
pysalesforceutils.PARTNER_SANDBOX_WSDL_FILE = '/path/to/partner_sandbox.wsdl'
```

Each WSDL file is only loaded once and then reused, because loading one is slow.

Some WSDLs that Salesforce generates refer to types they never define. For example, the version 68.0 Metadata WSDL uses `PolicyRulePrincipalDomain` and three other types for the `PolicyRule` metadata type without defining them. When the library loads a WSDL, it adds any missing type as one that accepts any content, so the file loads and every operation works. Only the fields of those types have no fixed structure. Your WSDL file isn't changed.
