# Tooling API

[Back to the README](../README.md)

The `Tooling` class wraps the Salesforce Tooling API, which is used to build development tools: running Apex, running tests, and reading or changing development records such as Apex classes and trace flags.

With the [Salesforce client](authentication.md#the-salesforce-client), the same methods are on `sf.tooling`, without the `access_token` and `instance_url` arguments.

- [Running anonymous Apex](#running-anonymous-apex)
- [Queries](#queries)
- [Running Apex tests](#running-apex-tests)
- [Tooling records](#tooling-records)
- [Code completions](#code-completions)

## Running anonymous Apex

```python
from pysalesforceutils import Tooling

result = Tooling.execute_anonymous("System.debug('Hello');", access_token, instance_url)

if not result['compiled']:
    print(result['compileProblem'], 'at line', result['line'])
elif not result['success']:
    print(result['exceptionMessage'])
```

The result tells you whether the code compiled and whether it ran without an exception. The code is sent as part of the url, so very long scripts can be too large for Salesforce to accept.

## Queries

`Tooling.query(query_string, ...)` runs a SOQL query against the Tooling API objects, such as `ApexClass`, `ApexTrigger` and `EntityDefinition`.

```python
from pysalesforceutils import Tooling

response = Tooling.query("SELECT Id, Name FROM ApexClass WHERE Name LIKE 'Account%'", access_token, instance_url)

for apex_class in response['records']:
    print(apex_class['Id'], apex_class['Name'])
```

## Running Apex tests

| Method | What it does |
|---|---|
| `run_tests_asynchronous_list(class_ids, suite_ids, max_failed_tests, test_level, ...)` | Runs the tests in the given classes or suites |
| `run_tests_asynchronous_json(test_array, ...)` | Runs tests with more control, such as choosing the test methods in each class |

Both start the tests and return the Id of the test run without waiting for it to finish.

```python
from pysalesforceutils import Tooling

# every test in two classes, by their comma separated class Ids
test_run_id = Tooling.run_tests_asynchronous_list('01pxx0000000001,01pxx0000000002', None, None, None,
                                                  access_token, instance_url)

# specific test methods
tests = [{'classId': '01pxx0000000001', 'testMethods': ['testInsert', 'testUpdate']}]
test_run_id = Tooling.run_tests_asynchronous_json(tests, access_token, instance_url)

# check on the results
query = "SELECT ApexClass.Name, MethodName, Outcome, Message FROM ApexTestResult WHERE AsyncApexJobId = '" + test_run_id + "'"
response = Tooling.query(query, access_token, instance_url)
```

Use `None` for any of `class_ids`, `suite_ids`, `max_failed_tests` and `test_level` that you don't need. `test_level` can be `RunSpecifiedTests`, `RunLocalTests` or `RunAllTestsInOrg`.

## Tooling records

These methods read and change single Tooling API records.

| Method | Returns |
|---|---|
| `get_sobject_row(object_name, record_id, ...)` | The record as a dict |
| `create_sobject_row(object_name, record_json, ...)` | A dict that includes the `id` of the new record |
| `update_sobject_row(object_name, record_id, record_json, ...)` | `'Update Successful'` |
| `delete_sobject_row(object_name, record_id, ...)` | `'Delete Successful'` |

```python
from pysalesforceutils import Tooling

apex_class = Tooling.get_sobject_row('ApexClass', apex_class_id, access_token, instance_url)
print(apex_class['Body'])

Tooling.delete_sobject_row('TraceFlag', trace_flag_id, access_token, instance_url)
```

## Code completions

`Tooling.completions(completions_type, ...)` returns the code completions for Apex system methods. Use `'apex'` for the type.
