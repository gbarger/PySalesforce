#!/usr/bin/python3

# TODO: 
# implement splitting of large batches to avoid breaking 10k limit with bulk jobs
# implement return of bulk job status record details
# implement delete in WebService so I can implement SObject Rows REST API for record deletes
# Figure out what's wrong with Tooling.completions
# Possibly pull current version from https://yourInstance.salesforce.com/services/data/ - ? Maybe not because of deprecation breaking methods

import json
import WebService
import urllib
import time

apiVersion = '37.0'

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
    ##
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
    ##
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
    ##
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
    ##
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
# The purpose of this class is to expose the Salesforce Tooling API methods
##
class Tooling:
    baseToolingUri = '/services/data/v' + apiVersion + '/tooling'

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
    ##
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
    ##
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
    ##
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
    ##
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
    ##
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
##
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
    ##
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
    ##
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
    ##
    def getSObjectRow(object, recordId, fieldListString, accessToken, instanceUrl):
        getRowUri = '/sobjects/' + object + '/' + recordId
        headerDetails = Util.getStandardHeader(accessToken)

        if fieldListString != None:
            getRowUri = getRowUri + '?fields=' + fieldListString

        response = WebService.Tools.getHTResponse(instanceUrl + Standard.baseStandardUri + 'v' + apiVersion + getRowUri, headerDetails)
        jsonResponse = json.loads(response.text)

        return jsonResponse

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
    ##
    def updateSObjectRow(object, recordId, recordJson, accessToken, instanceUrl):
        patchRowUri = '/sobjects/' + object + '/' + recordId
        headerDetails = Util.getStandardHeader(accessToken)

        dataBodyJson = json.dumps(recordJson, indent=4, separators=(',', ': '))

        response = WebService.Tools.patchHTResponse(instanceUrl + Standard.baseStandardUri + 'v' + apiVersion + patchRowUri, dataBodyJson, headerDetails)
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
    ##
    def query(queryString, accessToken, instanceUrl):
        queryUri = '/query/?q='
        headerDetails = Util.getStandardHeader(accessToken)
        urlEncodedQuery = urllib.parse.quote(queryString)

        response = WebService.Tools.getHTResponse(instanceUrl + Standard.baseStandardUri + 'v' + apiVersion + queryUri + urlEncodedQuery, headerDetails)
        jsonResponse = json.loads(response.text)

        return jsonResponse

##
# This class is used for doing bulk operations. Please use this and not the Standard 
# class singular methods when you're performing DML operations. This is faster and 
# will use fewer of your API calls.
# API details here: https://developer.salesforce.com/docs/atlas.en-us.api_asynch.meta/api_asynch/asynch_api_intro.htm
# examples here: https://trailhead-salesforce-com.firelayers.net/en/api_basics/api_basics_bulk
##
class Bulk:
    baseBulkUri = '/services/async/' + apiVersion

    ##
    # This method is used for printing job status
    ##
    def getJobStatus(jobId, pollingWait, accessToken, instanceUrl):
        statusUri = '/job'
        headerDetails = Util.getBulkHeader(accessToken)

        print("Status check for job: {}".format(jobId))
        while True:
            response = WebService.Tools.getHTResponse(instanceUrl + Bulk.baseBulkUri + statusUri + '/' + jobId, headerDetails)
            jsonResponse = json.loads(response.text)

            print("batches completed/total: {}/{}".format(jsonResponse['numberBatchesCompleted'], jsonResponse['numberBatchesTotal']))

            if jsonResponse['numberBatchesQueued'] is 0:
                break
            else:
                time.sleep(pollingWait)

        return jsonResponse

    ##
    # This method updates a list of records provided as an object.
    #
    # @param objectApiName  The API Name of the object being updated
    # @param records        The list of records that needs to be updated. This
    #                       Should be provided as an array. For example:
    #                       [{'id':'recordId', 'phone':'(123) 456-7890'}]
    # @param pollingWait    This is the number of seconds
    # @param accessToken    This is the access_token value received from the 
    #                       login response
    # @param instanceUrl    This is the instance_url value received from the 
    #                       login response
    ##
    def updateSObjectRows(objectApiName, records, pollingWait, accessToken, instanceUrl):
        bulkUpdateUri = '/job'
        headerDetails = Util.getBulkHeader(accessToken)
        bodyDetails = Util.getBulkJobBody(objectApiName, 'update', None, None)

        # create the batch job
        createJobJsonBody = json.dumps(bodyDetails, indent=4, separators=(',', ': '))
        jobCreateResponse = WebService.Tools.postHTResponse(instanceUrl + Bulk.baseBulkUri + bulkUpdateUri, createJobJsonBody, headerDetails)
        jsonJobCreateResponse = json.loads(jobCreateResponse.text)

        # send the records as a batch
        jobId = jsonJobCreateResponse['id']
        recordsJson = json.dumps(records, indent=4, separators=(',', ': '))
        jobBatchResponse = WebService.Tools.postHTResponse(instanceUrl + Bulk.baseBulkUri + bulkUpdateUri + '/' + jobId + '/batch', recordsJson, headerDetails)
        jsonJobBatchResponse = json.loads(jobBatchResponse.text)

        # close the batch
        closeBody = {'state': 'Closed'}
        jsonCloseBody = json.dumps(closeBody, )
        closeResponse = WebService.Tools.postHTResponse(instanceUrl + Bulk.baseBulkUri + bulkUpdateUri + '/' + jobId, jsonCloseBody, headerDetails)
        jsonCloseResponse = json.loads(closeResponse.text)

        if pollingWait != None:
            Bulk.getJobStatus(jobId, pollingWait, accessToken, instanceUrl)

        return jsonCloseResponse