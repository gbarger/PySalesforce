##PySalesforce
**************

The purpose of this project is to replicate the Salesforce REST APIs in a Python library.

As I work on replicating the APIs, I'll link to the Salesforce documentation here.
- [Tooling API](https://developer.salesforce.com/docs/atlas.en-us.api_tooling.meta/api_tooling/intro_rest_resources.htm)
- [REST API](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/intro_what_is_rest_api.htm)

##Notes
*******
I had issues with OS X not being able to connect to any sandbox environments. The issue was related to my OpenSSL version not being up to date enough.

You can run this test to check if your machine is up to date with SSL. Make sure it can run TLS 1.1 or 1.2
---
import WebService
response = WebService.Tools.getHTResponse("https://www.howsmyssl.com/a/check", {})
print(response.text)
---