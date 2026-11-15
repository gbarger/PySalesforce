# Bulk APIs

[Back to the README](../README.md)

The Bulk APIs load or query large numbers of records asynchronously: you create a job, Salesforce processes it in the background, and you collect the results when it's done. They use far fewer API calls than the [Standard REST API](standard.md) for large data sets.

- [Which one to use](#which-one-to-use)
- [Bulk API 2.0 loads](#bulk-api-20-loads)
- [Bulk API 2.0 queries](#bulk-api-20-queries)
- [Bulk API](#bulk-api)

## Which one to use

| Class | Data format | How it works |
|---|---|---|
| `Bulk2` | CSV | You create the job, upload the data and collect the results in separate steps. This is the API Salesforce recommends for new work. |
| `Bulk` | Lists of dicts | One method call creates the job, splits the records into batches, waits, and returns the results. |

With the [Salesforce client](authentication.md#the-salesforce-client), the same methods are on `sf.bulk2` and `sf.bulk`, without the `access_token` and `instance_url` arguments.

## Bulk API 2.0 loads

| Method | What it does |
|---|---|
| `create_job(object_name, operation, external_id_field_name, column_delimiter, content_type, line_ending, ...)` | Creates a job. The operation is `insert`, `update`, `upsert` or `delete`. |
| `upload_csv_batch(data_set, job_id, ...)` | Uploads the CSV data for the job. Returns the status code, which is 201 if it worked. |
| `change_job_state(job_state, job_id, ...)` | Use `'UploadComplete'` to start processing, or `'Aborted'` to cancel the job |
| `get_job_info(job_id, ...)` | Returns the current state of the job |
| `get_job_status(job_id, polling_wait, verbose, ...)` | Waits for the job to finish and returns its final state |
| `get_success_results(job_id, ...)` | Returns a CSV of the records that were processed |
| `get_failed_results(job_id, ...)` | Returns a CSV of the records that failed, with the error for each |
| `get_unprocessed_results(job_id, ...)` | Returns a CSV of the records that weren't processed |
| `delete_job(job_id, ...)` | Deletes a finished job |
| `get_job_list(is_pk_chunking_enabled, job_type, query_locator, ...)` | Lists the jobs in the org |

```python
from pysalesforceutils import Bulk2

csv_data = 'Name,Phone\nCloudy Consulting,(123) 456-7890\nEasy Spaces,(123) 555-0100\n'

job = Bulk2.create_job('Account', 'insert', None, None, None, None, access_token, instance_url)
job_id = job['id']

Bulk2.upload_csv_batch(csv_data, job_id, access_token, instance_url)
Bulk2.change_job_state('UploadComplete', job_id, access_token, instance_url)

job_info = Bulk2.get_job_status(job_id, 5, False, access_token, instance_url)
print(job_info['state'], job_info['numberRecordsProcessed'], job_info['numberRecordsFailed'])

failed_csv = Bulk2.get_failed_results(job_id, access_token, instance_url)
```

- The four `None` arguments to `create_job` are `external_id_field_name`, `column_delimiter`, `content_type` and `line_ending`. Use `None` to get Salesforce's defaults. `external_id_field_name` is required for an `upsert`.
- `get_job_status` checks the job every `polling_wait` seconds. Set `verbose` to `True` to print the state on each check.
- A job is finished when its state is `JobComplete`, `Failed` or `Aborted`.

## Bulk API 2.0 queries

| Method | What it does |
|---|---|
| `create_query_job(query, query_all, ...)` | Creates a job that runs a SOQL query. Set `query_all` to `True` to include deleted records. |
| `get_query_job_info(job_id, ...)` | Returns the current state of the job |
| `get_query_job_status(job_id, polling_wait, verbose, ...)` | Waits for the job to finish and returns its final state |
| `get_query_job_results(job_id, locator, max_records, ...)` | Returns one set of records as CSV, and the locator for the next set |
| `abort_query_job(job_id, ...)` | Cancels the job |
| `delete_query_job(job_id, ...)` | Deletes a finished job |

```python
from pysalesforceutils import Bulk2

job = Bulk2.create_query_job('SELECT Id, Name FROM Account', False, access_token, instance_url)
job_id = job['id']

Bulk2.get_query_job_status(job_id, 5, False, access_token, instance_url)

locator = None

while True:
    results = Bulk2.get_query_job_results(job_id, locator, None, access_token, instance_url)
    csv_data = results['records']
    # ... save or process csv_data here ...

    locator = results['locator']

    if locator is None:
        break
```

Large results come back in several sets. Each call returns the `locator` for the next set, and `None` when there are no more. Every set starts with its own header row. `max_records` limits how many records are in each set, and `None` lets Salesforce decide.

## Bulk API

The original Bulk API methods take the records as a list of dicts and handle the whole job in one call.

| Method | What it does |
|---|---|
| `insert_sobject_rows(object_api_name, records, batch_size, polling_wait, ..., concurrency_mode=None)` | Inserts the records |
| `update_sobject_rows(object_api_name, records, batch_size, polling_wait, ..., concurrency_mode=None)` | Updates the records. Each record needs its `Id`. |
| `upsert_sobject_rows(object_api_name, records, batch_size, polling_wait, ..., external_id_field_name='Id', concurrency_mode=None)` | Inserts or updates the records by an external Id field |
| `delete_sobject_rows(object_api_name, records, hard_delete, batch_size, polling_wait, ...)` | Deletes the records. Each record needs its `Id`. |
| `query_sobject_rows(object_api_name, query, query_all, ..., verbose=True)` | Runs a query and returns the records as a list |

```python
from pysalesforceutils import Bulk

records = [{'Name': 'Cloudy Consulting'}, {'Name': 'Easy Spaces'}]

results = Bulk.insert_sobject_rows('Account', records, 1000, 5, access_token, instance_url)

for result in results:
    print(result['success'], result['id'], result['errors'])

accounts = Bulk.query_sobject_rows('Account', 'SELECT Id, Name FROM Account', False, access_token, instance_url)
```

- `batch_size` is how many records go in each batch. 5,000 records with a batch size of 1,000 makes 5 batches.
- `polling_wait` is how many seconds to wait between checks on the job. `None` uses 5 seconds.
- `concurrency_mode` can be `'Parallel'` (the default) or `'Serial'`. Use `'Serial'` if the job fails because of record locking.
- `hard_delete` skips the Recycle Bin. The user needs the "Bulk API Hard Delete" permission.
- The results are in the same order as the records.
- These methods print the progress of the job while they wait.

The lower level methods `perform_bulk_operation`, `get_job_status`, `get_batch_result` and `get_query_result` are also available if you need more control. See their docstrings for the arguments.
