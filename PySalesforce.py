#!/usr/bin/python3

# TODO:
# implement metadata API
#     after metadata API implementation, update picklist tool to grab object without needing to do that separately
# refactor to clean up and reduce code for bulk query
# maybe implement kwargs for some of the methods instead of having so many arguments in the signature
# implement delete in WebService so I can implement SObject Rows REST API for record deletes
# Figure out what's wrong with Tooling.completions
# Work on Metadata API
# Possibly pull current version from https://yourInstance.salesforce.com/services/data/ - ? Maybe not because of deprecation breaking methods

import json
import WebService
import urllib
import time
import sys
from zeep import Client
from zeep import xsd
from zeep import ns

API_VERSION = '39.0'
METADATA_WSDL_FILE = './WSDL/metadata.wsdl'
METADATA_SANDBOX_WSDL_FILE = './WSDL/metadata_sandbox.wsdl'
METADATA_SERVICE_BINDING = '{http://soap.sforce.com/2006/04/metadata}MetadataBinding'
PARTNER_WSDL_FILE = './WSDL/partner.wsdl'
PARTNER_SANDBOX_WSDL_FILE = './WSDL/partner_sandbox.wsdl'

##
# This is a collection of utilities that will need to be reused bye the methods
# within the classes.
##
class Util:
    ##
    # This method will be used to generated headers. The documentation shows 
    # that there are header options availble, but doesn't do a good job of 
    # explaining what they're for or what they do, so I'm leaving this here to
    # generate the headers. For now it will just be a static header with the 
    # accessToken and X-PrettyPrint.
    #
    # @param accessToken        This is the access_token value received from the 
    #                           login response
    # @return                   Returns a header that has the required values for
    #                           the standard API.
    #
    def getStandardHeader(accessToken):
        # return {'Authorization': 'Bearer ' + accessToken,'X-PrettyPrint':1}
        objectHeader = {"Authorization": "Bearer " + accessToken,"Content-Type": "application/json"}
        return objectHeader

    ##
    # @param accessToken        This is the access_token value received from the 
    #                           login response
    # @return                   Returns a header that has the required values for
    #                           the bulk API. Namely, this takes the standard 
    #                           header and adds gzip encoding, which is recommended
    #                           by Salesforce to reduce the size of the responses.
    #                           This works becuase requests will automatically
    #                           unzip the zipped responses.
    #
    def getBulkHeader(accessToken):
        bulkHeader = Util.getStandardHeader(accessToken)
        bulkHeader['X-SFDC-Session'] = accessToken
        #bulkHeader['Content-Encoding'] = 'gzip'
        return bulkHeader

    ##
    # This method will be used to generate the bulk job body that is then used to 
    # send operation batches to Salesforce for processing. This is
    #
    # @param objectApiName      REQUIRED: The object name this job will perform
    #                           operations on
    # @param operationType      REQUIRED: This is the type of operation that will 
    #                           be run with this request. Possible values include: 
    #                               delete, insert, query, upsert, update, and hardDelete
    # @param assignmentRuleId   The ID of a specific assignment rule to run for 
    #                           a case or a lead. The assignment rule can be active 
    #                           or inactive.
    # @param concurrencyMode    Can't update after creation. The concurrency mode 
    #                           for the job. The valid values are:
    #                               Parallel: Process batches in parallel mode. 
    #                                   This is the default value.
    #                               Serial: Process batches in serial mode. 
    #                                   Processing in parallel can cause database 
    #                                   contention. When this is severe, the job 
    #                                   may fail. If you're experiencing this issue, 
    #                                   submit the job with serial concurrency mode. 
    #                                   This guarantees that batches are processed 
    #                                   one at a time. Note that using this option 
    #                                   may significantly increase the processing 
    #                                   time for a job.
    # @param externalIdFieldName  REQUIRED WITH UPSERT. The name of the external 
    #                             ID field for an upsert().
    # @param numberRetries      The number of times that Salesforce attempted to 
    #                           save the results of an operation. The repeated 
    #                           attempts are due to a problem, such as a lock 
    #                           contention.
    # @param jobState           REQUIRED IF CREATING, CLOSING OR ABORIGN A JOB. 
    #                           The current state of processing for the job:
    #                           Values:
    #                               Open: The job has been created, and batches 
    #                                   can be added to the job.
    #                               Closed: No new batches can be added to this 
    #                                   job. Batches associated with the job may 
    #                                   be processed after a job is closed. You 
    #                                   cannot edit or save a closed job.
    #                               Aborted: The job has been aborted. You can 
    #                                   abort a job if you created it or if you 
    #                                   have the “Manage Data Integrations” 
    #                                   permission.
    #                               Failed: The job has failed. Batches that were 
    #                                   successfully processed can't be rolled back. 
    #                                   The BatchInfoList contains a list of all 
    #                                   batches for the job. From the results of 
    #                                   BatchInfoList, results can be retrieved 
    #                                   for completed batches. The results indicate 
    #                                   which records have been processed. The 
    #                                   numberRecordsFailed field contains the 
    #                                   number of records that were not processed 
    #                                   successfully.
    #
    def getBulkJobBody(objectApiName, operationType, assignmentRuleId=None, concurrencyMode=None, externalIdFieldName=None, numberRetries=None, jobState=None):
        bulkJobBody = {'operation': operationType, 'object': objectApiName, 'contentType': 'JSON'}

        if assignmentRuleId != None:
            bulkJobBody['assignmentRuleId'] = assignmentRuleId

        if concurrencyMode != None:
            bulkJobBody['concurrencyMode'] = concurrencyMode

        if externalIdFieldName != None:
            bulkJobBody['externalIdFieldName'] = externalIdFieldName

        if numberRetries != None:
            bulkJobBody['numberRetries'] = numberRetries

        if jobState != None:
            bulkJobBody['state'] = jobState

        return bulkJobBody

    ##
    # This generator breaks up a list into a list of lists that contains n items
    # in each list.
    #
    # @param list   The list provided to be chunked
    # @param n      The number of items in each chunk
    #
    def chunk(list, n):
        for i in range(0, len(list), n):
            yield list[i:i + n]

    ##
    # Pass the wsdl and generate the soap client for the given WSDL
    #
    # @param wsdlFile       The file location for the WSDL used to generate the 
    #                       client
    # @return               Returns the SOAP client.
    #
    def getSoapClient(wsdlFile):
        soap_client = Client(wsdlFile)
        return soap_client

    def getSoapClientService(wsdlFile, serviceBinding, endpointUrl):
        soap_client = Util.getSoapClient(wsdlFile)
        soap_client_service = soap_client.create_service(serviceBinding, endpointUrl)

        return soap_client_service

##
# The Authentication class is used to log in and out of Salesforce
#
class Authentication:
    ##
    # this function logs into Salesforce using the oAuth 2.0 password grant type, and 
    # returns the response that can be used for other salesforce api requests. There
    # are two parts of the response that will be needed, the token, and the instance 
    # url. The token can be retrieved with jsonResponse['access_token'], and the 
    # instance url with jsonResponse['instance_url']. In order for this function to 
    # work, a connected app must be set up in Salesforce, which is where the client 
    # id and client secret come from the Client Id is the connected app Consumer 
    # Key, and the client secret is the consumer secret.
    #
    # @param loginUsername        this is the salesforce login
    # @param loginPassword        this is the salesforce password AND security token
    # @param loginClientId        this is the client Id from the oAuth settings in 
    #                             the Salesforce app setup
    # @param loginClientSecret    this is the secret from the oAuth settings in 
    #                             the Salesforce app setup
    # @param isProduction         this is a boolean value to set whether or not the 
    #                             base oAuth connection will be in production or 
    #                             a sandbox environment
    # @return                     returns the json from the login response body
    #                             the important aspects of the response are the 
    #                             access_token, which will be used to authenticate
    #                             the other calls, and instance_url, which is the
    #                             base endpoint used for the other calls
    #
    def getOAuthLogin(loginUsername, loginPassword, loginClientId, loginClientSecret, isProduction):
        if isProduction:
            baseOAuthUrl = 'https://login.salesforce.com/services/oauth2/token'
        else:
            baseOAuthUrl = 'https://test.salesforce.com/services/oauth2/token'

        loginBodyData = {'grant_type':'password','client_id':loginClientId,'client_secret':loginClientSecret,'username':loginUsername, 'password':loginPassword}

        response = WebService.Tools.postHTResponse(baseOAuthUrl, loginBodyData, '')

        try:
            jsonResponse = json.loads(response.text)
        except:
            jsonResponse = response.text

        return jsonResponse

    ##
    # this function calls the correct endpoint for the oauth logout by providing 
    # the token and whether or not the login is production or test.
    #
    # @param authToken            this is the token received in the access_token
    #                             response from the getOAuthLogin function.
    # @param isProduction         this is a boolean value to set whether or not 
    #                             the base oAuth connection will be in production
    #                             or a sandbox environment.
    # @return                     returns a json response with success (True or 
    #                             False), and the status_code returned by the 
    #                             call to revoke the token
    #
    def getOAuthLogout(authToken, isProduction):
        if isProduction:
            logoutUrl = 'https://login.salesforce.com/services/oauth2/revoke'
        else:
            logoutUrl = 'https://test.salesforce.com/services/oauth2/revoke'

        logoutBodyData = {'host':logoutUrl,'Content-Type':'application/x-www-form-urlencoded','token':authToken}

        response = WebService.Tools.postHTResponse(logoutUrl, logoutBodyData, '')

        success = False
        if response.status_code == 200:
            success = True

        jsonResponse = {'success':success,'status_code':response.status_code}

        return jsonResponse

    ##
    # Only use this for authenticating as a self-service user
    #
    # @param orgId          The ID of the organization against which you will
    #                       authenticate Self-Service users.
    # @param portalId       Specify only if user is a Customer Portal user. The
    #                       ID of the portal for this organization.
    # @return               Returns the ScopeHeader for SOAP login requests.
    #
    def getLoginScopeHeader(orgId, portalId):
        login_scope_header = {}
        login_scope_header['organizationId'] = orgId

        if portalId != None:
            login_scope_header['portalId'] = portalId

        return login_scope_header

    ##
    # This creates the call options for the SOAP login.
    #
    # @param clientName     A string that identifies a client. 
    # @param defaultNS      A string that identifies a developer namespace 
    #                       prefix. Use this field to resolve field names in
    #                       managed packages without having to fully specify
    #                       the fieldName everywhere.
    # @return               Returns the CallOptions for SOAP login requests.
    #
    def getLoginCallOptions(clientName, defaultNS):
        call_options = {}

        if clientName != None:
            call_options['client'] = clientName

        if defaultNS != None:
            call_options['defaultNamespace'] = defaultNS

        return call_options

    ##
    # This method builds the headers for soap calls. Leave orgId and 
    # portalId as None if you are using a normal authentication. These
    # values are only used for self-service authentication
    #
    # @param orgId          The ID of the organization against which you will
    #                       authenticate Self-Service users.
    # @param portalId       Specify only if user is a Customer Portal user. The
    #                       ID of the portal for this organization.
    # @param clientName     A string that identifies a client.
    # @param defaultNS      A string that identifies a developer namespace 
    #                       prefix. Use this field to resolve field names in
    #                       managed packages without having to fully specify
    #                       the fieldName everywhere.
    # @return               Returns the SOAP headers needed to log in
    #
    def getSoapHeaders(orgId, portalId, clientName, defaultNS):
        client = Util.getSoapClient(PARTNER_WSDL_FILE)
        soap_headers = {}

        if orgId != None or portalId != None:
            login_scope = Authentication.getLoginScopeHeader(orgId, portalId)
            soap_headers['LoginScopeHeader'] = login_scope

        if clientName != None or defaultNS != None:
            call_options = Authentication.getLoginCallOptions(clientName, defaultNS)
            soap_headers['CallOptions'] = call_options

        return soap_headers

    ##
    # This method logs into Salesforce with SOAP given the provided details.
    # Only use orgId and portalId for self-service user authentication. For 
    # most purposes, these should be set to None. The clientName is actually a
    # clientId used for partner applications and the defaultNS is the default
    # namespace used for an application. So these values can also be set to None
    # for most requests. For most requests, you will only need the username and
    # password.
    #
    # @param loginUsername        this is the salesforce login
    # @param loginPassword        this is the salesforce password AND security 
    #                             token
    # @param orgId                The ID of the organization against which you 
    #                             will authenticate Self-Service users.
    # @param portalId             Specify only if user is a Customer Portal 
    #                             user. The ID of the portal for this 
    #                             organization.
    # @param clientName           A string that identifies a client. Used for 
    #                             partner applications.
    # @param defaultNS            A string that identifies a developer namespace 
    #                             prefix. Use this field to resolve field names
    #                             in managed packages without having to fully 
    #                             specify the fieldName everywhere.
    # @param isProduction         this is a boolean value to set whether or not 
    #                             the base oAuth connection will be in production
    #                             or a sandbox environment.
    # @return                     returns a long response object that contains
    #                             the session id login_result['sessionId'], 
    #                             metadata server url login_result['metadataServerUrl']
    #                             and server url login_result['serverUrl']
    #
    def getSoapLogin(loginUsername, loginPassword, orgId, portalId, clientName, defaultNS, isProduction):
        wsdl_file = PARTNER_WSDL_FILE

        if not(isProduction):
            wsdl_file = PARTNER_SANDBOX_WSDL_FILE

        client = Util.getSoapClient(wsdl_file)
        soap_headers = Authentication.getSoapHeaders(orgId, portalId, clientName, defaultNS)
        login_result = client.service.login(loginUsername, loginPassword, _soapheaders=soap_headers)

        return login_result

##
# The purpose of this class is to expose the Salesforce Tooling API methods
##
class Tooling:
    baseToolingUri = '/services/data/v' + API_VERSION + '/tooling'

    ##
    # Retrieves available code completions of the referenced type for Apex system 
    # method symbols (type=apex).
    #
    # @param completionsType     The type of metadata to get completions for. 
    #                            e.g. 'apex'
    # @param accessToken         This is the access_token value received from the 
    #                            login response
    # @param instanceUrl         This is the instance_url value received from the 
    #                            login response
    # @return                    Returns the completion values for the specified 
    #                            type like apex.
    #
    def completions(completionsType, accessToken, instanceUrl):
        completionsUri = '/completions?type='
        headerDetails = Util.getStandardHeader(accessToken)
        urlEncodedType = urllib.parse.quote(completionsType)

        response = WebService.Tools.getHTResponse(instanceUrl + Tooling.baseToolingUri + completionsUri + urlEncodedType, headerDetails)
        jsonResponse = json.loads(response.text)

        return jsonResponse

    ##
    # this function executes anonymous apex, and returns a json response object.
    # The response should contain a success value (True or False), column and 
    # line numbers, which return -1 if there are no issues, exceptionStackTrace 
    # which should be None if there are no problems, compiled (True or False), 
    # compileProblem which should be None if there are no problems, and 
    # exceptionMessage if an exception was thrown.
    #
    # @param codeString          this is the non url encoded code string that you
    #                            would like to execute
    # @param accessToken         This is the access_token value received from the 
    #                            login response
    # @param instanceUrl         This is the instance_url value received from the 
    #                            login response
    # @return                    returns the response result from executing the 
    #                            salesforce script
    #
    def executeAnonymous(codeString, accessToken, instanceUrl):
        executeAnonymousUri = '/executeAnonymous/?anonymousBody='
        headerDetails = Util.getStandardHeader(accessToken)
        urlEncodedCode = urllib.parse.quote(codeString)

        response = WebService.Tools.getHTResponse(instanceUrl + Tooling.baseToolingUri + executeAnonymousUri + urlEncodedCode, headerDetails)
        jsonResponse = json.loads(response.text)

        return jsonResponse

    ##
    # Executes a query against an object and returns data that matches the 
    # specified criteria. Tooling API exposes objects like EntityDefinition and 
    # FieldDefinition that use the external object framework--that is, they don’t 
    # exist in the database but are constructed dynamically. Special query rules 
    # apply to virtual entities. If the query result is too large, it’s broken up 
    # into batches. The response contains the first batch of results and a query 
    # identifier. The identifier can be used in a request to retrieve the next 
    # batch. A list of the tooling api objects can be found here: 
    # https://developer.salesforce.com/docs/atlas.en-us.api_tooling.meta/api_tooling/reference_objects_list.htm
    #
    # @param queryString         the query to be executed
    # @param accessToken         This is the access_token value received from the 
    #                            login response
    # @param instanceUrl         This is the instance_url value received from the 
    #                            login response
    # @return                    returns a JSON object with the results of the 
    #                            query.
    #
    def query(queryString, accessToken, instanceUrl):
        queryUri = '/query/?q='
        headerDetails = Util.getStandardHeader(accessToken)
        urlEncodedQuery = urllib.parse.quote(queryString)

        response = WebService.Tools.getHTResponse(instanceUrl + Tooling.baseToolingUri + queryUri + urlEncodedQuery, headerDetails)
        jsonResponse = json.loads(response.text)

        return jsonResponse

    ##
    # This method runs the tests provided with the class Ids or suite Ids, then 
    # returns the direct results from the Salesforce tooling API.
    #
    # @param classIds           List of comma separated class Ids to run the tests
    # @param suiteIds           List of suite ids to run
    # @param maxFailedTests     The max number of failed tests
    # @param maxFailedTests     To stop the test run from executing new tests 
    #                           after a given number of tests fail, set to an 
    #                           integer value from 0 to 1,000,000. To allow all 
    #                           tests in your run to execute, regardless of how 
    #                           many tests fail, omit maxFailedTests or set it
    #                           to -1
    # @param testLevel          The testLevel parameter is optional. If you don’t 
    #                           provide a testLevel value, we use RunSpecifiedTests.
    #                           values:
    #                               RunSpecifiedTests - Only the tests that you 
    #                                   specify are run.
    #                               RunLocalTests - All tests in your org are run, 
    #                                   except the ones that originate from installed
    #                                   managed packages. Omit identifiers for 
    #                                   specific tests when you use this value.
    #                               RunAllTestsInOrg - All tests are run. The 
    #                                   tests include all tests in your org, 
    #                                   including tests of managed packages. Omit 
    #                                   identifiers for specific tests when you 
    #                                   use this value.
    # @param accessToken        This is the access_token value received from the 
    #                           login response
    # @param instanceUrl        This is the instance_url value received from the 
    #                           login response
    # @return                   returns the Id of the test run
    #
    def runTestsAsynchronousList(classIds, suiteIds, maxFailedTests, testLevel, accessToken, instanceUrl):
        testAsyncUri = '/runTestsAsynchronous/'
        headerDetails = Util.getStandardHeader(accessToken)

        dataBody = {}

        if classIds != None:
            dataBody['classids'] = classIds

        if suiteIds != None:
            dataBody['suiteids'] = suiteIds

        if maxFailedTests != None:
            dataBody['maxFailedTests'] = maxFailedTests

        if testLevel != None:
            dataBody['testLevel'] = testLevel

        jsonDataBody = json.dumps(dataBody, indent=4, separators=(',', ': '))

        response = WebService.Tools.postHTResponse(instanceUrl + Tooling.baseToolingUri + testAsyncUri, jsonDataBody, headerDetails)
        jsonResponse = json.loads(response.text)

        return jsonResponse

    ##
    # This method runs specified tests in the testArray with more control than 
    # the runTestsAsynchronousList method by allowing you to specify which methods
    # you'd like to run with each test class.
    #
    # @param testArray      This is an array of tests that you'd like to run with
    #                       the specified methods if you wish. Like the 
    #                       runTestsAsynchronousList method, you can also specify
    #                       the maxFailedTests and testLevel values
    #                       e.g.
    #                           [
    #                             {"classId": "01pD0000000Fhy9IAC",
    #                              "testMethods": ["testMethod1","testMethod2", "testMethod3"]},
    #                             {"classId": "01pD0000000FhyEIAS",
    #                              "testMethods": ["testMethod1","testMethod2", "testMethod3"]},
    #                             {"maxFailedTests": "2"},
    #                             {"testLevel": "RunSpecifiedTests"}
    #                           ]
    # @param accessToken    This is the access_token value received from the 
    #                       login response
    # @param instanceUrl    This is the instance_url value received from the 
    #                       login response
    # @return               returns the Id of the test run
    #
    def runTestsAsynchronousJson(testArray, accessToken, instanceUrl):
        testAsyncUri = '/runTestsAsynchronous/'
        headerDetails = Util.getStandardHeader(accessToken)
        dataBody = {'tests': testArray}
        jsonDataBody = json.dumps(dataBody, indent=4, separators=(',', ': '))

        response = WebService.Tools.postHTResponse(instanceUrl + Tooling.baseToolingUri + testAsyncUri, jsonDataBody, headerDetails)
        jsonResponse = json.loads(response.text)

        return jsonResponse

##
# This class provides a front end for the Salesforce standard REST API. More details
# about this can be found here: https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/intro_what_is_rest_api.htm
# You can get more details about each of the methods by looking in the reference
# section of the documentation.
#
class Standard:
    baseStandardUri = '/services/data/'

    ##
    # Lists summary information about each Salesforce version currently available, 
    # including the version, label, and a link to each version's root.
    #
    # @param accessToken    This is the access_token value received from the 
    #                       login response
    # @param instanceUrl    This is the instance_url value received from the 
    #                       login response
    # @return               Returns an object with the list of Salesforce versions
    #
    def versions(accessToken, instanceUrl):
        headerDetails = Util.getStandardHeader(accessToken)

        response = WebService.Tools.getHTResponse(instanceUrl + Standard.baseStandardUri, headerDetails)
        jsonResponse = json.loads(response.text)

        return jsonResponse

    ##
    # This method returns the available resources (API services) available for 
    # the supplied version number.
    #
    # @param versionNumString   This is the version number as a string, e.g. 37.0
    # @param accessToken        This is the access_token value received from the 
    #                           login response
    # @param instanceUrl        This is the instance_url value received from the 
    #                           login response
    # @return                   Returns an object containing the list of availble
    #                           reousrces for this version number.
    #
    def resourcesByVersion(versionNumString, accessToken, instanceUrl):
        headerDetails = Util.getStandardHeader(accessToken)

        response = WebService.Tools.getHTResponse(instanceUrl + Standard.baseStandardUri + 'v' + versionNumString + '/', headerDetails)
        jsonResponse = json.loads(response.text)

        return jsonResponse

    ##
    # Provides the details requested for the specified record. In practice, if you
    # provide an explicit list of fields, it will be just like a query for that
    # record, but if you leave the fields blank, this will return a lot if not
    # all fields. I'm not sure about that because the description of what is 
    # returned if you leave the fields empty isn't explaind in the API documentaiton
    #
    # @param object           The API name of the object.
    # @param recordId         The record Id you're trying to retreive
    # @param fieldListString  List of comma separated values for fields to retrieve
    # @param accessToken      This is the access_token value received from the 
    #                         login response
    # @param instanceUrl      This is the instance_url value received from the 
    #                         login response
    # @param return           returns the record with the explicit field list, or
    #                         all (or a lot) of the fields if the fieldListString
    #                         is None.
    #
    def getSObjectRow(object, recordId, fieldListString, accessToken, instanceUrl):
        getRowUri = '/sobjects/' + object + '/' + recordId
        headerDetails = Util.getStandardHeader(accessToken)

        if fieldListString != None:
            getRowUri = getRowUri + '?fields=' + fieldListString

        response = WebService.Tools.getHTResponse(instanceUrl + Standard.baseStandardUri + 'v' + API_VERSION + getRowUri, headerDetails)
        jsonResponse = json.loads(response.text)

        return jsonResponse

    ##
    # Creates the provided record in the recordJson paaram
    #
    # @param object         The API name of the object.
    # @param recordJson     The JSON describing the fields you want to update on
    #                       the given object. You should pass in a python object
    #                       and it will be converted to a json string to send the
    #                       request. This object is just the key value paris
    #                       for the record update. e.g.:
    #                           {
    #                               'BillingCity': 'Bellevue',
    #                               'BillingState': 'WA'
    #                           }
    # @param instanceUrl    This is the instance_url value received from the 
    #                       login response
    #
    def createSObjectRow(object, recordJson, accessToken, instanceUrl):
        patchRowUri = '/sobjects/' + object + '/'
        headerDetails = Util.getStandardHeader(accessToken)

        dataBodyJson = json.dumps(recordJson, indent=4, separators=(',', ': '))

        response = WebService.Tools.postHTResponse(instanceUrl + Standard.baseStandardUri + 'v' + API_VERSION + patchRowUri, dataBodyJson, headerDetails)
        responseText = ""

        if response.status_code is 204:
            responseText = "Update Successful"
        else:
            responseText = response.text

        return responseText

    ##
    # Updates a specific record with the data in the recordJson param
    #
    # @param object         The API name of the object.
    # @param recordId       The record Id you're trying to update
    # @param recordJson     The JSON describing the fields you want to update on
    #                       the given object. You should pass in a python object
    #                       and it will be converted to a json string to send the
    #                       request. This object is just the key value paris
    #                       for the record update. e.g.:
    #                           {
    #                               'BillingCity': 'Bellevue',
    #                               'BillingState': 'WA'
    #                           }
    # @param accessToken    This is the access_token value received from the 
    #                       login response
    # @param instanceUrl    This is the instance_url value received from the 
    #                       login response
    # @param return         This only returns 'Update Successful' if the update 
    #                       worked, or returns an error message if the update 
    #                       wasn't successful. The response isn't more detailed
    #                       because Salesforce returns no text, only a response
    #                       code of 204
    #
    def updateSObjectRow(object, recordId, recordJson, accessToken, instanceUrl):
        patchRowUri = '/sobjects/' + object + '/' + recordId
        headerDetails = Util.getStandardHeader(accessToken)

        dataBodyJson = json.dumps(recordJson, indent=4, separators=(',', ': '))

        response = WebService.Tools.patchHTResponse(instanceUrl + Standard.baseStandardUri + 'v' + API_VERSION + patchRowUri, dataBodyJson, headerDetails)
        responseText = ""

        if response.status_code is 204:
            responseText = "Update Successful"
        else:
            responseText = response.text

        return responseText

    ##
    # Executes the specified SOQL query. If the query results are too large, the 
    # response contains the first batch of results and a query identifier in the 
    # nextRecordsUrl field of the response. The identifier can be used in an 
    # additional request to retrieve the next batch.
    #
    # @param queryString    This query you'd like to run
    # @param accessToken    This is the access_token value received from the 
    #                       login response
    # @param instanceUrl    This is the instance_url value received from the 
    #                       login response
    # @return               returns the query results, if they are too large, 
    #                       then it will also return a nextRecordsUrl to get
    #                       more records.
    #
    def query(queryString, accessToken, instanceUrl):
        queryUri = '/query/?q='
        headerDetails = Util.getStandardHeader(accessToken)
        urlEncodedQuery = urllib.parse.quote(queryString)

        response = WebService.Tools.getHTResponse(instanceUrl + Standard.baseStandardUri + 'v' + API_VERSION + queryUri + urlEncodedQuery, headerDetails)
        jsonResponse = json.loads(response.text)

        return jsonResponse

##
# This class is used for doing bulk operations. Please use this and not the Standard 
# class singular methods when you're performing DML operations. This is faster and 
# will use fewer of your API calls.
# API details here: https://developer.salesforce.com/docs/atlas.en-us.api_asynch.meta/api_asynch/asynch_api_intro.htm
# examples here: https://trailhead-salesforce-com.firelayers.net/en/api_basics/api_basics_bulk
#
class Bulk:
    baseBulkUri = '/services/async/' + API_VERSION
    batchUri = '/job/'

    ##
    # This method is used for printing job status
    #
    # @param jobId          The job id returned when creating a batch job
    # @param pollingWait    This is the number of seconds
    # @param accessToken    This is the access_token value received from the 
    #                       login response
    # @param instanceUrl    This is the instance_url value received from the 
    #                       login response
    # @return               Prints the status of the bulk job and polls for an 
    #                       update ever pollingWait seconds until the 
    #                       numberBatchesQueued = 0, then it will break out and
    #                       just returns the final job status response.
    #
    def getJobStatus(jobId, pollingWait, accessToken, instanceUrl):
        headerDetails = Util.getBulkHeader(accessToken)

        print("Status for job: {}".format(jobId))
        while True:
            response = WebService.Tools.getHTResponse(instanceUrl + Bulk.baseBulkUri + Bulk.batchUri + '/' + jobId, headerDetails)
            jsonResponse = json.loads(response.text)

            print("batches completed/total: {}/{}".format(jsonResponse['numberBatchesCompleted'], jsonResponse['numberBatchesTotal']))

            if jsonResponse['numberBatchesCompleted'] == jsonResponse['numberBatchesTotal']:
                break
            else:
                time.sleep(pollingWait)

        return jsonResponse

    ##
    # This method will retrieve the results of a batch operation.
    #
    # @param jobId          The job id returned when creating a batch job
    # @param batchId        This is the batch Id returned when creating a new batch
    # @param accessToken    This is the access_token value received from the 
    #                       login response
    # @param instanceUrl    This is the instance_url value received from the 
    #                       login response
    # @return               Returns the an array containing the results for each
    #                       record in the given batch
    #
    def getBatchResult(jobId, batchId, accessToken, instanceUrl):
        headerDetails = Util.getBulkHeader(accessToken)

        response = WebService.Tools.getHTResponse(instanceUrl + Bulk.baseBulkUri + Bulk.batchUri + '/' + jobId + '/batch/' + batchId + '/result', headerDetails)
        jsonResponse = json.loads(response.text)

        return jsonResponse

    ##
    # This method will retrieve the results of a batch operation.
    #
    # @param jobId          The job id returned when creating a batch job
    # @param batchId        This is the batch Id returned when creating a new batch
    # @param queryResultId  Ths is the Id returned with a successful batch for 
    #                       a Salseforce bulk query.
    # @param accessToken    This is the access_token value received from the 
    #                       login response
    # @param instanceUrl    This is the instance_url value received from the 
    #                       login response
    # @return               Returns the an array containing the results for the 
    #                       query request
    #
    def getQueryResult(jobId, batchId, queryResultId, accessToken, instanceUrl):
        headerDetails = Util.getBulkHeader(accessToken)

        response = WebService.Tools.getHTResponse(instanceUrl + Bulk.baseBulkUri + Bulk.batchUri + '/' + jobId + '/batch/' + batchId + '/result' + '/' + queryResultId, headerDetails)
        jsonResponse = json.loads(response.text)

        return jsonResponse

    ##
    # This method updates a list of records provided as an object.
    #
    # @param objectApiName  The API Name of the object being updated
    # @param records        The list of records that needs to be updated. This
    #                       Should be provided as an array. For example:
    #                       [{'id':'recordId', 'phone':'(123) 456-7890'}]
    # @param batchSize      This is the batch size of the records to process. 
    #                       If you were to pass 5000 records into the process 
    #                       with a batch size of 1000, then there would be 5 
    #                       batches processed.
    # @param operationType  This is the operation being performed: 
    #                           delete, insert, query, upsert, update, hardDelete
    # @param pollingWait    This is the number of seconds to poll for updates on 
    #                       the job
    # @param accessToken    This is the access_token value received from the 
    #                       login response
    # @param instanceUrl    This is the instance_url value received from the 
    #                       login response
    # @return               Returns an object containing the status for each 
    #                       record that was put into the batch
    #
    def performBulkOperation(objectApiName, records, batchSize, operationType, pollingWait, externalIdFieldName, accessToken, instanceUrl):
        headerDetails = Util.getBulkHeader(accessToken)
        bodyDetails = {}

        if externalIdFieldName != None:
            bodyDetails = Util.getBulkJobBody(objectApiName, operationType, None, None, externalIdFieldName)
        else:
            bodyDetails = Util.getBulkJobBody(objectApiName, operationType, None, None)

        chunkedRecordsList = Util.chunk(records, batchSize)
        batchIds = []
        resultsList = []

        # create the bulk job
        createJobJsonBody = json.dumps(bodyDetails, indent=4, separators=(',', ': '))
        jobCreateResponse = WebService.Tools.postHTResponse(instanceUrl + Bulk.baseBulkUri + Bulk.batchUri, createJobJsonBody, headerDetails)
        jsonJobCreateResponse = json.loads(jobCreateResponse.text)
        jobId = jsonJobCreateResponse['id']

        # loop through the record batches, and add them to the processing queue
        for recordChunk in chunkedRecordsList:
            recordsJson = json.dumps(recordChunk, indent=4, separators=(',', ': '))
            jobBatchResponse = WebService.Tools.postHTResponse(instanceUrl + Bulk.baseBulkUri + Bulk.batchUri + '/' + jobId + '/batch', recordsJson, headerDetails)
            jsonJobBatchResponse = json.loads(jobBatchResponse.text)
            batchId = jsonJobBatchResponse['id']
            batchIds.append(batchId)

        # close the bulk job
        closeBody = {'state': 'Closed'}
        jsonCloseBody = json.dumps(closeBody, )
        closeResponse = WebService.Tools.postHTResponse(instanceUrl + Bulk.baseBulkUri + Bulk.batchUri + '/' + jobId, jsonCloseBody, headerDetails)
        jsonCloseResponse = json.loads(closeResponse.text)

        # set default job check polling to 5 seconds
        if pollingWait is None:
            pollingWait = 5
        
        # check job status until the job completes
        Bulk.getJobStatus(jobId, pollingWait, accessToken, instanceUrl)

        # populate the resultsList by appending the results of each batch
        for thisBatchId in batchIds:
            batchResults = Bulk.getBatchResult(jobId, thisBatchId, accessToken, instanceUrl)
            resultsList.extend(batchResults)

        return resultsList

    ##
    # This method inserts a list of records provided as an object.
    #
    # @param objectApiName  The API Name of the object being updated
    # @param records        The list of records that needs to be updatbatchSize, ed. This
    #                       Should be provided as an array. For example:
    #                       [{'id':'recordId', 'phone':'(123) 456-7890'}]
    # @param batchSize      This is the batch size of the records to process. 
    #                       If you were to pass 5000 records into the process 
    #                       with a batch size of 1000, then there would be 5 
    #                       batches processed.
    # @param pollingWait    This is the number of seconds
    # @param accessToken    This is the access_token value received from the 
    #                       login response
    # @param instanceUrl    This is the instance_url value received from the 
    #                       login response
    # @return               Returns an object containing the status for each 
    #                       record that was put into the batch
    #
    def insertSObjectRows(objectApiName, records, batchSize, pollingWait, accessToken, instanceUrl):
        result = Bulk.performBulkOperation(objectApiName, records, batchSize, 'insert', pollingWait, None, accessToken, instanceUrl)

        return result

    ##
    # This method updates a list of records provided as an object.
    #
    # @param objectApiName  The API Name of the object being updated
    # @param records        The list of records that needs to be updated. This
    #                       Should be provided as an array. For example:
    #                       [{'id':'recordId', 'phone':'(123) 456-7890'}]
    # @param batchSize      This is the batch size of the records to process. 
    #                       If you were to pass 5000 records into the process 
    #                       with a batch size of 1000, then there would be 5 
    #                       batches processed.
    # @param pollingWait    This is the number of seconds
    # @param accessToken    This is the access_token value received from the 
    #                       login response
    # @param instanceUrl    This is the instance_url value received from the 
    #                       login response
    # @return               Returns an object containing the status for each 
    #                       record that was put into the batch
    #
    def updateSObjectRows(objectApiName, records, batchSize, pollingWait, accessToken, instanceUrl):
        result = Bulk.performBulkOperation(objectApiName, records, batchSize, 'update', pollingWait, None, accessToken, instanceUrl)

        return result

    ##
    # This method upserts a list of records provided as an object.
    #
    # @param objectApiName  The API Name of the object being updated
    # @param records        The list of records that needs to be updated. This
    #                       Should be provided as an array. For example:
    #                       [{'id':'recordId', 'phone':'(123) 456-7890'}]
    # @param batchSize      This is the batch size of the records to process. 
    #                       If you were to pass 5000 records into the process 
    #                       with a batch size of 1000, then there would be 5 
    #                       batches processed.
    # @param pollingWait    This is the number of seconds
    # @param accessToken    This is the access_token value received from the 
    #                       login response
    # @param instanceUrl    This is the instance_url value received from the 
    #                       login response
    # @param externalIdFieldName  This is the external Id field that is used to 
    #                             determine whether this record will be inserted
    #                             or updated. This is required for upserts, but 
    #                             will default to the record Id field
    # @return               Returns an object containing the status for each 
    #                       record that was put into the batch
    #
    def upsertSObjectRows(objectApiName, records, batchSize, pollingWait, accessToken, instanceUrl, externalIdFieldName='Id'):
        result = Bulk.performBulkOperation(objectApiName, records, batchSize, 'upsert', pollingWait, externalIdFieldName, accessToken, instanceUrl)

        return result

    ##
    # This method upserts a list of records provided as an object.
    #
    # @param objectApiName  The API Name of the object being updated
    # @param records        The list of records that needs to be updated. This
    #                       Should be provided as an array. For example:
    #                       [{'id':'recordId', 'phone':'(123) 456-7890'}]
    # @param hardDelete     This Bool indicates whether or not the record should 
    #                       be hard deleted. NOTE: There is a profile System 
    #                       Permission option called "Bulk API Hard Delete"
    #                       that must be enabled for this option to work.
    # @param batchSize      This is the batch size of the records to process. 
    #                       If you were to pass 5000 records into the process 
    #                       with a batch size of 1000, then there would be 5 
    #                       batches processed.
    # @param pollingWait    This is the number of seconds
    # @param accessToken    This is the access_token value received from the 
    #                       login response
    # @param instanceUrl    This is the instance_url value received from the 
    #                       login response
    # @return               Returns an object containing the status for each 
    #                       record that was put into the batch
    #
    def deleteSObjectRows(objectApiName, records, hardDelete, batchSize, pollingWait, accessToken, instanceUrl):
        deleteType = 'delete';

        if hardDelete:
            deleteType = 'hardDelete'

        result = Bulk.performBulkOperation(objectApiName, records, batchSize, deleteType, pollingWait, None, accessToken, instanceUrl)

        return result

    ##
    # This returns the result for a bulk query operations.
    #
    # @param objectApiName  The API Name of the object being updated
    # @param query          The query you'd like to run to retrieve records
    # @param accessToken    This is the access_token value received from the 
    #                       login response
    # @param instanceUrl    This is the instance_url value received from the 
    #                       login response
    # @return               Returns an array of results for the specified query
    #
    def querySObjectRows(objectApiName, query, queryAll, accessToken, instanceUrl):
        headerDetails = Util.getBulkHeader(accessToken)
        batchResultsList = []
        queryResultList = []

        queryType = 'query'

        if queryAll:
            queryType = 'queryAll'
        
        # create the bulk job
        jobBodyDetails = Util.getBulkJobBody(objectApiName, queryType, None, None)
        createJobJsonBody = json.dumps(jobBodyDetails, indent=4, separators=(',', ': '))
        jobCreateResponse = WebService.Tools.postHTResponse(instanceUrl + Bulk.baseBulkUri + Bulk.batchUri, createJobJsonBody, headerDetails)
        jsonJobCreateResponse = json.loads(jobCreateResponse.text)
        jobId = jsonJobCreateResponse['id']

        # create the query request batch
        jobBatchResponse = WebService.Tools.postHTResponse(instanceUrl + Bulk.baseBulkUri + Bulk.batchUri + '/' + jobId + '/batch', query, headerDetails)
        jsonJobBatchResponse = json.loads(jobBatchResponse.text)
        batchId = jsonJobBatchResponse['id']
        print("\nbatchId: {}\n".format(batchId))

        # close the bulk job
        closeBody = {'state': 'Closed'}
        jsonCloseBody = json.dumps(closeBody, )
        closeResponse = WebService.Tools.postHTResponse(instanceUrl + Bulk.baseBulkUri + Bulk.batchUri + '/' + jobId, jsonCloseBody, headerDetails)
        jsonCloseResponse = json.loads(closeResponse.text)

        # check job status until the job completes
        Bulk.getJobStatus(jobId, 5, accessToken, instanceUrl)

        # get results
        batchResults = Bulk.getBatchResult(jobId, batchId, accessToken, instanceUrl)
        batchResultsList.extend(batchResults)

        for queryResultId in batchResultsList:
            queryResult = Bulk.getQueryResult(jobId, batchId, queryResultId, accessToken, instanceUrl)
            queryResultList.extend(queryResult)

        return queryResultList

class Metadata:

    ##
    # Used to get the session header for the given sessionId
    #
    # @param sessionId      The session ID that the login call returns.
    #
    def getSessionHeader(sessionId):
        client = Util.getSoapClient(METADATA_WSDL_FILE)
        session_header_element = client.get_element('ns0:SessionHeader')
        session_header = session_header_element(sessionId)

        return session_header

    ##
    # This returns the call options for the soap header
    #
    # @param clientName     A value that identifies an API client.
    #
    def getCallOptions(clientName):
        client = Util.getSoapClient(METADATA_WSDL_FILE)
        call_options_element = client.get_element('ns0:CallOptions')
        call_options = call_options_element(clientName)

        return call_options

    ##
    # Indicates whether to roll back all metadata changes when some of the 
    # records in a call result in failures.
    #
    # @param allOrNone      Set to true to cause all metadata changes to be
    #                       rolled back if any records in the call cause 
    #                       failures. Set to false to enable saving only the
    #                       records that are processed successfully when other
    #                       records in the call cause failures.
    #
    def getAllOrNoneHeader(allOrNone):
        client = Util.getSoapClient(METADATA_WSDL_FILE)
        all_or_none_header_element = client.get_element('ns0:AllOrNoneHeader')
        all_or_none_header = all_or_none_header_element(allOrNone)

        return all_or_none_header

    ##
    # Specifies that the deployment result will contain the debug log output,
    # and specifies the level of detail included in the log. The debug log
    # contains the output of Apex tests that are executed as part of a
    # deployment.
    #
    # @param categories     A list of log categories with their associated log 
    #                       levels.
    #
    def getDebuggingHeader(categories):
        client = Util.getSoapClient(METADATA_WSDL_FILE)
        debugging_header_element = client.get_element('ns0:DebuggingHeader')
        debugging_header = debugging_header_element(categories, None)

        return debugging_header

    ##
    # This builds the session header for the Metadata requests
    #
    # @param sessionId          The session ID that the login call returns.
    # @param clientName         A value that identifies an API client.
    # @param allOrNone          Set to true to cause all metadata changes to be
    #                           rolled back if any records in the call cause 
    #                           failures. Set to false to enable saving only the
    #                           records that are processed successfully when other
    #                           records in the call cause failures.
    # @param debugCategories    A list of log categories with their associated
    #                           log levels.
    #
    def getSoapHeaders(sessionId, clientName, allOrNone, debugCategories):
        soap_headers = {}
        soap_headers['SessionHeader'] = Metadata.getSessionHeader(sessionId)

        if clientName != None:
            soap_headers['CallOptions'] = Metadata.getCallOptions(clientName)

        if allOrNone != None:
            soap_headers['AllOrNoneHeader'] = Metadata.getAllOrNoneHeader(allOrNone)

        if debugCategories != None:
            soap_headers['DebuggingHeader'] = Metadata.getDebuggingHeader()


        return soap_headers

    ##
    # This builds the list of members for a specific type. For example this wil
    # store the list of all the ApexClass members you want to reference. Only a
    #
    # @param memberName         This is the Metadata type being referenced.
    #                           A list of types can be found here:
    #                           https://developer.salesforce.com/docs/atlas.en-us.api_meta.meta/api_meta/meta_types_list.htm
    # @param memberList         An array of the members you're working with in 
    #                           the package.
    def getPackageTypeMembers(memberName, memberList):
        package_type_members = {}
        package_type_members['name'] = memberName
        package_type_members['members'] = memberList

        return package_type_members

    ##
    # This method builds the client service for the Metadata API
    #
    # @param metadataUrl          The Url used to send this request to
    #
    def getClientService(metadataUrl):
        soap_client_service = Util.getSoapClientService(METADATA_WSDL_FILE, METADATA_SERVICE_BINDING, metadataUrl)

        return soap_client_service

    ##
    # Specifies which metadata components to retrieve as part of a retrieve() 
    # call or defines a package of components.
    #
    # @param fullName              The package name used as a unique identifier
    #                              for API access. The fullName can contain
    #                              only underscores and alphanumeric characters.
    #                              It must be unique, begin with a letter, not
    #                              include spaces, not end with an underscore,
    #                              and not contain two consecutive underscores.
    #                              This field is inherited from the Metadata
    #                              component.
    # @param apiAccessLevel        Package components have access via dynamic
    #                              Apex and the API to standard and custom
    #                              objects in the organization where they are
    #                              installed. Administrators who install
    #                              packages may wish to restrict this access 
    #                              after installation for improved security.
    #                              The valid values are:
    #                                * Unrestricted—Package components have
    #                                  the same API access to standard objects
    #                                  as the user who is logged in when the
    #                                  component sends a request to the API.
    #                                * Restricted—The administrator can select
    #                                  which standard objects the components
    #                                  can access. Further, the components in
    #                                  restricted packages can only access 
    #                                  custom objects in the current package
    #                                  if the user's permissions allow access
    #                                  to them.
    #                              For more information, see “About API and
    #                              Dynamic Apex Access in Packages” in the
    #                              Salesforce online help.
    # @param description           A short description of the package.
    # @param namespacePrefix       The namespace of the developer organization
    #                              where the package was created.
    # @param objectPermissions     Indicates which objects are accessible to
    #                              the package, and the kind of access available
    #                              (create, read, update, delete).
    # @param packageType           Reserved for future use.
    # @param postInstallClass      The name of the Apex class that specifies
    #                              the actions to execute after the package has
    #                              been installed or upgraded. The Apex class
    #                              must be a member of the package and must
    #                              implement the Apex InstallHandler interface.
    #                              In patch upgrades, you can't change the class
    #                              name in this field but you can change the 
    #                              contents of the Apex class. The class name
    #                              can be changed in major upgrades.
    #                              This field is available in API version 24.0
    #                              and later.
    # @param setupWeblink          The weblink used to describe package
    #                              installation.
    # @param types                 The type of component being retrieved. You
    #                              can build the types with the 
    #                              getPackageTypeMembers() method.
    # @param uninstallClass        The name of the Apex class that specifies
    #                              the actions to execute after the package has
    #                              been uninstalled. The Apex class must be a 
    #                              member of the package and must implement the
    #                              Apex UninstallHandler interface. In patch
    #                              upgrades, you can't change the class name in
    #                              this field but you can change the contents of
    #                              the Apex class. The class name can be changed
    #                              in major upgrades.
    #                              This field is available in API version 25.0
    #                              and later.
    # @param version               Required. The version of the component type.
    #
    def getPackage(**kwargs):
        if kwargs.get('version') is None:
            print('The version parameter is required to create a package.')
            sys.exit(0)

        client = Util.getSoapClient(METADATA_WSDL_FILE)
        package_type = client.get_type('ns0:Package')
        this_package = package_type(
            kwargs.get('fullName'),
            kwargs.get('apiAccessLevel'),
            kwargs.get('description'),
            kwargs.get('namespacePrefix'),
            kwargs.get('objectPermissions'),
            kwargs.get('packageType'),
            kwargs.get('postInstallClass'),
            kwargs.get('setupWeblink'),
            kwargs.get('types'),
            kwargs.get('uninstallClass'),
            kwargs.get('version')
        )

        return this_package

    ##
    # This is the package of data needed to retrieve metadata
    #
    # @param apiVersion         Required. The API version for the retrieve 
    #                           request. The API version determines the fields
    #                           retrieved for each metadata type. For example,
    #                           an icon field was added to the CustomTab for
    #                           API version 14.0. If you retrieve components
    #                           for version 13.0 or earlier, the components
    #                           will not include the icon field.
    # @param packageNames       A list of package names to be retrieved. If you
    #                           are retrieving only unpackaged components, do
    #                           not specify a name here. You can retrieve
    #                           packaged and unpackaged components in the same
    #                           retrieve.
    # @param singlePackage      Specifies whether only a single package is
    #                           being retrieved (true) or not (false). If false,
    #                           then more than one package is being retrieved.
    # @param specificFiles      A list of file names to be retrieved. If a value
    #                           is specified for this property, packageNames
    #                           must be set to null and singlePackage must be
    #                           set to true.
    # @param unpackaged         A list of components to retrieve that are not
    #                           in a package. You can build the package using
    #                           the getPackage() method.
    #
    def getRetrieveRequest(**kwargs):
        if kwargs.get('apiVersion') is None:
            print('The version parameter is required to create a package.')
            sys.exit(0)

        client = Util.getSoapClient(METADATA_WSDL_FILE)
        retrieveRequest_type = client.get_type('ns0:RetrieveRequest')
        this_retrieveRequest = retrieveRequest_type(
            kwargs.get('apiVersion'),
            kwargs.get('packageNames'),
            kwargs.get('singlePackage'),
            kwargs.get('specificFiles'),
            kwargs.get('unpackaged')
        )

        return this_retrieveRequest

    ##
    # This returns the async result of a retrieve request that can then be used
    # to check the retrieve status
    #
    # @param retrieveRequest        The request settings which can be created
    #                               using the getRetrieveRequest() method
    # @param sessionId              The session ID that the login call returns.
    # @param clientName             A value that identifies an API client. This
    #                               is used for partner applications
    #
    def retrieve(retrieveRequest, sessionId, metadataUrl, clientName):
        soap_headers = Metadata.getSoapHeaders(sessionId, clientName, None, None)

        client_service = Metadata.getClientService(metadataUrl)
        this_retrieve = client_service.retrieve(retrieveRequest, _soapheaders=soap_headers)

        return this_retrieve


    ##
    # This checks the status of the retrieve request. You can have the response
    # include a zip file if you wish, or you can set that to false and get the
    # zip in a later response
    #
    # @param asyncProcessId       Required. The ID of the component that’s being
    #                             deployed or retrieved.
    # @param includeZip           This tells the process whether or not to 
    #                             include the zip file in the result or. Starting
    #                             with API version 34.0, pass a boolean value for
    #                             the includeZip argument of checkRetrieveStatus()
    #                             to indicate whether to retrieve the zip file.
    #                             The includeZip argument gives you the option to
    #                             retrieve the file in a separate process after
    #                             the retrieval operation is completed.
    # @param sessionId            The session ID that the login call returns.
    # @param metadataUrl          The Url used to send this request to
    # @param clientName           A value that identifies an API client. This is
    #                             used for partner applications
    #
    def checkRetrieveStatus(asyncProcessId, includeZip, sessionId, metadataUrl, clientName):
        soap_headers = Metadata.getSoapHeaders(sessionId, clientName, None, None)

        client_service = Metadata.getClientService(metadataUrl)
        this_retrieveStatus = client_service.checkRetrieveStatus(asyncProcessId, includeZip, _soapheaders=soap_headers)

        return this_retrieveStatus

    ##
    # This method cancels the deploy
    #
    # @param deployId             The Id returned from the deploy request
    # @param sessionId            The session ID that the login call returns.
    # @param metadataUrl          The Url used to send this request to
    # @param clientName           A value that identifies an API client. This is
    #                             used for partner applications
    #
    def cancelDeploy(deployId, sessionId, metadataUrl, clientName):
        soap_headers = Metadata.getSoapHeaders(sessionId, clientName, None, None)

        client_service = Metadata.getClientService(metadataUrl)
        cancel_deploy_result = client_service.cancelDeploy(deployId, _soapheaders=soap_headers)

        return cancelDeployResult

    ##
    # This method checks the status of the requested deploy
    #
    # @param deployId             The Id returned from the deploy request
    # @param includeDetails       Sets the DeployResult object to include 
    #                             DeployDetails information ((true) or not 
    #                             (false). The default is false. Available in
    #                             API version 29.0 and later.
    # @param sessionId            The session ID that the login call returns.
    # @param metadataUrl          The Url used to send this request to
    # @param clientName           A value that identifies an API client. This is
    #                             used for partner applications
    #
    def checkDeployStatus(deployId, includeDetails, sessionId, metadataUrl, clientName):
        soap_headers = Metadata.getSoapHeaders(sessionId, clientName, None, None)

        client_service = Metadata.getClientService(metadataUrl)
        check_deploy_result = client_service.checkDeployStatus(deployId, includeDetails, _soapheaders=soap_headers)

        return check_deploy_result

    def createMetadata():
        # createMetadata(metadata: ns0:Metadata[], _soapheaders={SessionHeader: ns0:SessionHeader, CallOptions: ns0:CallOptions, AllOrNoneHeader: ns0:AllOrNoneHeader})
        # ns0:Metadata(fullName: xsd:string) ==> is a type

        return True

    def deleteMetadata():
        # deleteMetadata(type: xsd:string, fullNames: xsd:string[], _soapheaders={SessionHeader: ns0:SessionHeader, CallOptions: ns0:CallOptions, AllOrNoneHeader: ns0:AllOrNoneHeader}) -> result: ns0:DeleteResult[]

        return True

    def deploy():
        # deploy(ZipFile: xsd:base64Binary, DeployOptions: ns0:DeployOptions, _soapheaders={SessionHeader: ns0:SessionHeader, DebuggingHeader: ns0:DebuggingHeader, CallOptions: ns0:CallOptions}) -> result: ns0:AsyncResult

        return True

    def deployRecentValidation():
        # deployRecentValidation(validationId: ns0:ID, _soapheaders={SessionHeader: ns0:SessionHeader, DebuggingHeader: ns0:DebuggingHeader, CallOptions: ns0:CallOptions}) -> result: xsd:string

        return True

    def describeMetadata():
        # describeMetadata(asOfVersion: xsd:double, _soapheaders={SessionHeader: ns0:SessionHeader, CallOptions: ns0:CallOptions}) -> result: ns0:DescribeMetadataResult

        return True

    def describeValueType():
        # describeValueType(type: xsd:string, _soapheaders={SessionHeader: ns0:SessionHeader}) -> result: ns0:DescribeValueTypeResult

        return True

    def listMetadata():
        # listMetadata(queries: ns0:ListMetadataQuery[], asOfVersion: xsd:double, _soapheaders={SessionHeader: ns0:SessionHeader, CallOptions: ns0:CallOptions}) -> result: ns0:FileProperties[]

        return True

    def readMetadata():
        # readMetadata(type: xsd:string, fullNames: xsd:string[], _soapheaders={SessionHeader: ns0:SessionHeader, CallOptions: ns0:CallOptions}) -> result: ns0:ReadResult

        return True

    def renameMetadata():
        # renameMetadata(type: xsd:string, oldFullName: xsd:string, newFullName: xsd:string, _soapheaders={SessionHeader: ns0:SessionHeader, CallOptions: ns0:CallOptions}) -> result: ns0:SaveResult

        return True

    def updateMetadata():
        # updateMetadata(metadata: ns0:Metadata[], _soapheaders={SessionHeader: ns0:SessionHeader, CallOptions: ns0:CallOptions, AllOrNoneHeader: ns0:AllOrNoneHeader}) -> result: ns0:SaveResult[]

        return True

    def upsertMetadata():
        # upsertMetadata(metadata: ns0:Metadata[], _soapheaders={SessionHeader: ns0:SessionHeader, CallOptions: ns0:CallOptions, AllOrNoneHeader: ns0:AllOrNoneHeader}) -> result: ns0:UpsertResult[]

        return True