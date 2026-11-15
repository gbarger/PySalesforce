# Composite requests

[Back to the README](../README.md)

Composite requests run several REST API requests in one call to Salesforce, which saves API calls and lets you roll the requests back together.

- [Which one to use](#which-one-to-use)
- [Building subrequests](#building-subrequests)
- [Composite request](#composite-request)
- [Batch request](#batch-request)
- [sObject tree](#sobject-tree)
- [Composite graph](#composite-graph)

## Which one to use

| Method on `Standard` | Use it when | Limit |
|---|---|---|
| `composite_request` | Later requests need the output of earlier ones, e.g. the Id of a record that was just created | 25 subrequests |
| `composite_batch_request` | The requests are independent of each other | 25 subrequests |
| `create_sobject_tree` | You're creating parent records together with their child records | 200 records |
| `graph_composite_request` | You need more subrequests than `composite_request` allows, or several groups that each succeed or fail on their own | 500 subrequests per graph |

For creating, updating or deleting many records of the same kind, the [multiple record methods](standard.md#multiple-records) are simpler.

## Building subrequests

A subrequest is a dict that describes one request. You can write the dicts by hand, or build them with the `Composite` class. Both work with every method on this page, and you can mix them in the same list.

```python
from pysalesforceutils import Composite

# built with the Composite class
subrequest = Composite.create('new_account', 'Account', {'Name': 'Cloudy Consulting'})

# the same subrequest written by hand
subrequest = {
    'method': 'POST',
    'url': '/services/data/v67.0/sobjects/Account/',
    'referenceId': 'new_account',
    'body': {'Name': 'Cloudy Consulting'}
}
```

The builders fill in the current API version and url encode the object names and Ids for you. They only build the dict. Nothing is sent to Salesforce until you pass the list to one of the `Standard` methods.

| Builder | The subrequest it builds |
|---|---|
| `Composite.create(reference_id, object_name, record_json)` | Creates a record |
| `Composite.update(reference_id, object_name, record_id, record_json)` | Updates a record |
| `Composite.upsert(reference_id, object_name, external_id_field_name, external_id, record_json)` | Creates or updates a record by its external Id |
| `Composite.delete(reference_id, object_name, record_id)` | Deletes a record |
| `Composite.get(reference_id, object_name, record_id, field_list_string=None)` | Gets a record |
| `Composite.query(reference_id, query_string)` | Runs a SOQL query |
| `Composite.request(reference_id, method, path, body=None)` | Calls any other resource. The `path` is the part of the url after `/services/data/vXX.X`. |
| `Composite.graph(graph_id, subrequests)` | Groups subrequests into one graph for `graph_composite_request` |

The `reference_id` is a name you choose for the subrequest. It is used to find its result in the response, and to refer to its output in a later subrequest with `@{reference_id.field}`. It can only contain letters, numbers and underscores.

## Composite request

```python
from pysalesforceutils import Composite, Standard

subrequests = [
    Composite.create('new_account', 'Account', {'Name': 'Cloudy Consulting'}),
    Composite.create('new_contact', 'Contact', {'LastName': 'Cashman', 'AccountId': '@{new_account.id}'}),
    Composite.get('saved_account', 'Account', '@{new_account.id}', 'Id,Name')
]

response = Standard.composite_request(subrequests, True, access_token, instance_url)

for result in response['compositeResponse']:
    print(result['referenceId'], result['httpStatusCode'], result['body'])
```

- The second argument is `all_or_none`. When it's `True`, all of the subrequests are rolled back if any of them fail.
- Salesforce may run the subrequests in a different order to make them faster. If the order matters for a reason Salesforce can't see, such as a trigger, pass `collate_subrequests=False`.
- Up to 5 of the 25 subrequests can be queries or multiple record requests.

## Batch request

The subrequests in a batch are independent. They can't refer to each other and they aren't rolled back together.

```python
from pysalesforceutils import Composite, Standard

subrequests = [
    Composite.update('update_account', 'Account', account_id, {'Name': 'New Name'}),
    Composite.get('get_contact', 'Contact', contact_id, 'Id,LastName'),
    Composite.request('limits', 'GET', '/limits')
]

response = Standard.composite_batch_request(subrequests, False, access_token, instance_url)

print(response['hasErrors'])

for result in response['results']:
    print(result['statusCode'], result['result'])
```

The second argument is `halt_on_error`. When it's `True`, Salesforce stops at the first subrequest that fails.

Salesforce uses a slightly different format for batch subrequests: the url starts at the version, the body is called `richInput`, and there is no `referenceId`. `composite_batch_request` accepts both formats and converts the composite format for you, so the builders work here too. A batch subrequest written by hand looks like this:

```python
subrequest = {
    'method': 'PATCH',
    'url': 'v67.0/sobjects/Account/001xx000003DGb2AAG',
    'richInput': {'Name': 'New Name'}
}
```

The results are in the same order as the subrequests.

## sObject tree

`create_sobject_tree` creates records together with their child records. If any record fails, none of them are created.

```python
from pysalesforceutils import Standard

records = [
    {
        'attributes': {'type': 'Account', 'referenceId': 'account_1'},
        'Name': 'Cloudy Consulting',
        'Contacts': {
            'records': [
                {'attributes': {'type': 'Contact', 'referenceId': 'contact_1'}, 'LastName': 'Cashman'},
                {'attributes': {'type': 'Contact', 'referenceId': 'contact_2'}, 'LastName': 'Smith'}
            ]
        }
    }
]

response = Standard.create_sobject_tree('Account', records, access_token, instance_url)

for result in response['results']:
    print(result['referenceId'], result['id'])
```

Each record needs an `attributes` value with its `type` and a `referenceId`. Child records go under the name of the child relationship, which is `Contacts` for the contacts of an account.

## Composite graph

A graph is a group of subrequests that succeed or fail together. One call can contain several graphs, and each graph is independent of the others.

```python
from pysalesforceutils import Composite, Standard

first_graph = [
    Composite.create('account_1', 'Account', {'Name': 'Cloudy Consulting'}),
    Composite.create('contact_1', 'Contact', {'LastName': 'Cashman', 'AccountId': '@{account_1.id}'})
]

second_graph = [
    Composite.create('account_2', 'Account', {'Name': 'Easy Spaces'})
]

request_body = {'graphs': [Composite.graph('graph_1', first_graph), Composite.graph('graph_2', second_graph)]}

response = Standard.graph_composite_request(request_body, access_token, instance_url)

for graph in response['graphs']:
    print(graph['graphId'], graph['isSuccessful'])

    for result in graph['graphResponse']['compositeResponse']:
        print(result['referenceId'], result['httpStatusCode'])
```

`graph_composite_request` takes the whole request body, so a body written by hand works as well.
