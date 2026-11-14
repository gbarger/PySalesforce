# PySalesforce
**************
The purpose of this project is to replicate the Salesforce REST APIs in a Python library.

## Usage
*******
The authentication method used in pysalesforceutils.Authentication.get_oauth_login uses the Salesforce OAuth Password flow. You can choose to build and use your own authentication method, but if you want to use the OAuth flow, you'll need to create a connected app in Salesforce. You can do this from Setup->Create->Apps, then scroll down to the bottom and click the New button for Connected Apps. The Callback URL is irrelevant, so you can put in anything you want. For the Selected OAuth Scopes, only grant what you need. "Manage user data via APIs (api)" is enough for the methods in this library, so avoid Full Access. After setting it up you'll receive a Consumer Key and Consumer Secret, which are the login_client_id and login_client_secret parameters in the get_oauth_login method respectively.

## Salesforce Documentation
***************
As I continue to update this library, I'll be adding reference links to the Salesforce documentation.
- [List of Salseforce APIs](https://developer.salesforce.com/page/Salesforce_APIs)
- [Tooling API](https://developer.salesforce.com/docs/atlas.en-us.api_tooling.meta/api_tooling/intro_rest_resources.htm)
- [Metadata API](https://developer.salesforce.com/page/An_Introduction_to_Force.com_Metadata)
- [Streaming API](https://developer.salesforce.com/page/Streaming_API)
- [REST API](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/intro_what_is_rest_api.htm)
- [Bulk API](https://developer.salesforce.com/docs/atlas.en-us.api_asynch.meta/api_asynch/asynch_api_intro.htm)
- [Bulk 2.0 API](https://developer.salesforce.com/docs/atlas.en-us.api_bulk_v2.meta/api_bulk_v2/introduction_bulk_api_2.htm)
- [Chatter REST API](https://developer.salesforce.com/page/Chatter_API)
- [Bulk API Trailhead Example](https://trailhead-salesforce-com.firelayers.net/en/api_basics/api_basics_bulk)

## Notes
*******
I had issues with OS X not being able to connect to any sandbox environments. The issue was related to my OpenSSL version not being up to date enough.

You can run this test to check if your machine is up to date with SSL. Make sure it can run TLS 1.1 or 1.2
---
from pysalesforceutils import webservice
response = webservice.Tools.get_http_response("https://www.howsmyssl.com/a/check", {})
print(response.text)
---