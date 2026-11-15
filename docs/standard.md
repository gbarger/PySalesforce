# Standard REST API

[Back to the README](../README.md)

The `Standard` class wraps the Salesforce REST API. The examples on this page use the static methods. With the [Salesforce client](authentication.md#the-salesforce-client), call the same method on `sf.standard` and leave out `access_token` and `instance_url`.

- [Queries and search](#queries-and-search)
- [Single records](#single-records)
- [Records by external Id](#records-by-external-id)
- [Multiple records](#multiple-records)
- [Files](#files)
- [Describing the org](#describing-the-org)
- [Changed records](#changed-records)
- [Actions and Apex REST](#actions-and-apex-rest)
- [Users and Chatter](#users-and-chatter)
- [Any other resource](#any-other-resource)

For composite, batch, tree and graph requests, see [Composite requests](composite.md).

## Queries and search

| Method | What it does |
|---|---|
| `query(query_string, ...)` | Runs a SOQL query and returns the first batch of results |
| `query_all(query_string, ...)` | The same, but includes deleted and archived records |
| `get_next_query_batch(next_record_url, ...)` | Gets the next batch, using `nextRecordsUrl` from the previous response |
| `query_records(query_string, ..., include_deleted=False)` | Runs a query and returns the records from every batch as one list |
| `query_explain(query_string, ...)` | Returns the query plans for a query without running it |
| `search(search_string, ...)` | Runs a SOSL search |
| `parameterized_search(search_body, ...)` | Runs a search described by a dict instead of a SOSL string |

```python
from pysalesforceutils import Standard, Util

# every record, however many batches it takes
accounts = Standard.query_records('SELECT Id, Name FROM Account', access_token, instance_url)

# one batch at a time
response = Standard.query('SELECT Id, Name FROM Account', access_token, instance_url)
records = response['records']

while 'nextRecordsUrl' in response:
    response = Standard.get_next_query_batch(response['nextRecordsUrl'], access_token, instance_url)
    records.extend(response['records'])
```

`query_records` keeps every record in memory. For very large results, use a [Bulk API 2.0 query job](bulk.md#bulk-api-20-queries).

When a value in a query comes from a user or another system, quote it with `Util.soql_quote` so it can't change the query:

```python
query = 'SELECT Id FROM Account WHERE Name = ' + Util.soql_quote(account_name)
accounts = Standard.query_records(query, access_token, instance_url)
```

## Single records

| Method | Returns |
|---|---|
| `get_sobject_row(object_name, record_id, field_list_string, ...)` | The record as a dict. Use `None` for the field list to get the default fields. |
| `create_sobject_row(object_name, record_json, run_assignment_rules, ...)` | The response body as text, which contains the new record Id |
| `update_sobject_row(object_name, record_id, record_json, run_assignment_rules, ...)` | `'Update Successful'` |
| `delete_sobject_row(object_name, record_id, ...)` | `'Delete Successful'` |

```python
import json
from pysalesforceutils import Standard

account = Standard.get_sobject_row('Account', record_id, 'Id,Name,Phone', access_token, instance_url)

response_text = Standard.create_sobject_row('Account', {'Name': 'Cloudy Consulting'}, False, access_token, instance_url)
new_id = json.loads(response_text)['id']

Standard.update_sobject_row('Account', new_id, {'Phone': '(123) 456-7890'}, False, access_token, instance_url)
Standard.delete_sobject_row('Account', new_id, access_token, instance_url)
```

`run_assignment_rules` sets whether the assignment rules for leads and cases run.

## Records by external Id

These methods find the record by the value of an external Id field instead of its record Id.

| Method | Returns |
|---|---|
| `get_sobject_row_by_external_id(object_name, external_id_field_name, external_id, field_list_string, ...)` | The record as a dict |
| `upsert_sobject_row_by_external_id(object_name, external_id_field_name, external_id, record_json, ...)` | A dict with `id`, `success`, `errors` and `created` |
| `delete_sobject_row_by_external_id(object_name, external_id_field_name, external_id, ...)` | `'Delete Successful'` |

```python
from pysalesforceutils import Standard

result = Standard.upsert_sobject_row_by_external_id('Account', 'External_Id__c', 'A-1001',
                                                    {'Name': 'Cloudy Consulting'}, access_token, instance_url)
print(result['created'])    # True if a new record was created
```

Don't include the external Id field in `record_json`, because its value comes from the `external_id` argument.

## Multiple records

These methods work on up to 200 records in one call. Each record needs an `attributes` value with its object `type`.

| Method | What it does |
|---|---|
| `create_sobject_rows(records, all_or_none, run_assignment_rules, ...)` | Creates the records |
| `update_sobject_rows(records, all_or_none, run_assignment_rules, ...)` | Updates the records. Each record also needs its `id`. |
| `upsert_sobject_rows(object_api_name, records, ..., all_or_none=False, run_assignment_rules=False, external_id_field_name='Id')` | Creates or updates records of one object by an external Id field |
| `delete_sobject_rows(record_ids, all_or_none, ...)` | Deletes the records in a list of Ids |
| `get_sobject_rows(object_name, record_id_list_string, field_list_string, ...)` | Gets records from comma separated Ids and fields |
| `retrieve(object_name, ids, fields, ...)` | Gets up to 2,000 records from a list of Ids and a list of fields |

```python
from pysalesforceutils import Standard

records = [
    {'attributes': {'type': 'Account'}, 'Name': 'Cloudy Consulting'},
    {'attributes': {'type': 'Contact'}, 'LastName': 'Cashman'}
]

results = Standard.create_sobject_rows(records, False, False, access_token, instance_url)

for result in results:
    print(result['success'], result.get('id'), result['errors'])

accounts = Standard.retrieve('Account', ['001xx000003DGb2AAG'], ['Id', 'Name'], access_token, instance_url)
```

When `all_or_none` is `True`, none of the records are saved if any of them fail. The results are in the same order as the records in the request.

For more than a few thousand records, use the [Bulk APIs](bulk.md).

## Files

| Method | What it does |
|---|---|
| `get_sobject_blob(object_name, record_id, ...)` | Downloads the file from an `Attachment`, `ContentVersion`, `Document` or `ContentNote`. Returns the HTTP response. |
| `create_sobject_blob_record(object_name, record_json, file, ...)` | Creates an `Attachment`, `ContentVersion` or `Document` from an open file |

```python
from pysalesforceutils import Standard

response = Standard.get_sobject_blob('ContentVersion', content_version_id, access_token, instance_url)

with open('report.pdf', 'wb') as new_file:
    new_file.write(response.content)

with open('report.pdf', 'rb') as file:
    record = {'Title': 'Report', 'PathOnClient': 'report.pdf'}
    Standard.create_sobject_blob_record('ContentVersion', record, file, access_token, instance_url)
```

The record must include the file name: `PathOnClient` for a `ContentVersion`, and `Name` for an `Attachment` or `Document`.

## Describing the org

| Method | What it does |
|---|---|
| `versions(...)` | Lists the API versions Salesforce supports |
| `resources_by_version(version_num_string, ...)` | Lists the resources available for a version, e.g. `'60.0'` |
| `get_global_describe(...)` | Lists all the objects in the org |
| `get_object_describe(object_name, modified_since_date, ...)` | Describes one object: its fields, relationships and urls |
| `get_limits(...)` | Lists the org limits with the maximum and the remaining amount for each |

```python
from pysalesforceutils import Standard

describe = Standard.get_object_describe('Account', None, access_token, instance_url)
field_names = [field['name'] for field in describe['fields']]

limits = Standard.get_limits(access_token, instance_url)
print(limits['DailyApiRequests']['Remaining'])
```

If you pass a `datetime` as `modified_since_date`, `get_object_describe` returns `None` when the object hasn't changed since then.

## Changed records

| Method | What it does |
|---|---|
| `get_updated(object_name, start_date_time, end_date_time, ...)` | Lists the Ids of records created or changed in the time span |
| `get_deleted(object_name, start_date_time, end_date_time, ...)` | Lists the Ids of records deleted in the time span |

Both take `datetime` values in UTC and only go back 30 days.

## Actions and Apex REST

| Method | What it does |
|---|---|
| `invoke_standard_action(action_name, inputs, ...)` | Runs a standard invocable action, e.g. `'emailSimple'` |
| `invoke_custom_action(action_type, action_name, inputs, ...)` | Runs a custom action, e.g. an autolaunched flow (`'flow'`) or an invocable Apex method (`'apex'`) |
| `apex_rest_request(method, path, ..., data=None)` | Calls a custom Apex REST service. Returns the HTTP response. |

```python
from pysalesforceutils import Standard

results = Standard.invoke_custom_action('flow', 'Close_Stale_Cases', [{'accountId': account_id}],
                                        access_token, instance_url)

response = Standard.apex_rest_request('POST', '/MyService/orders', access_token, instance_url, {'quantity': 2})
order = response.json()
```

`inputs` is a list, and the action runs once for each item in it. The `path` for `apex_rest_request` is the part of the url after `/services/apexrest`.

## Users and Chatter

| Method | What it does |
|---|---|
| `get_current_user_info(...)` | Returns information about the logged in user |
| `reset_users_password(user_id, ...)` | Resets a user's password |
| `post_chatter_mention(text, mention_id, subject_id, ...)` | Posts to a record's feed, mentioning a user or group |

## Any other resource

`Standard.request` calls any REST API resource for the current API version, so you can use resources that don't have their own method. It returns the HTTP response.

```python
from pysalesforceutils import Standard

response = Standard.request('GET', '/sobjects/Account/describe/layouts', access_token, instance_url)
layouts = response.json()

response = Standard.request('POST', '/sobjects/Account/', access_token, instance_url, {'Name': 'Cloudy Consulting'})
```

The `path` is the part of the url after `/services/data/vXX.X`. Unlike the other methods, `request` and `apex_rest_request` use the path exactly as you give it. If part of the path comes from a user or another system, encode it first with `urllib.parse.quote(value, safe='')`.
