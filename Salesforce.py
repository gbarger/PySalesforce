#!/Library/Frameworks/Python.framework/Versions/3.5/bin/python3

#TODO: Figure out what's wrong with Tooling.completions

import json
import WebService
import urllib

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
            jsonResponse = json.loads(response.data)
        except:
            jsonResponse = response.data

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

class Tooling:
    baseToolingUri = '/services/data/v37.0/tooling'

    ##
    # This method will be used to generated headers. The documentation shows 
    # that there are header options availble, but doesn't do a good job of 
    # explaining what they're for or what they do, so I'm leaving this here to
    # generate the headers. For now it will just be a static header with the 
    # accessToken and X-PrettyPrint.
    #
    # @param accessToken        This is the access_token value received from the 
    #                           login response
    #
    def getToolingHeader(accessToken):
        # return {'Authorization': 'Bearer ' + accessToken,'X-PrettyPrint':1}
        return {'Authorization': 'Bearer ' + accessToken,'Content-Type': 'application/json'}

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
    ##
    def completions(completionsType, accessToken, instanceUrl):
        completionsUri = '/completions?type='
        headerDetails = Tooling.getToolingHeader(accessToken)
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
    ##
    def executeAnonymous(codeString, accessToken, instanceUrl):
        executeAnonymousUri = '/executeAnonymous/?anonymousBody='
        headerDetails = Tooling.getToolingHeader(accessToken)
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
    # batch.
    #
    # @param queryString         the query to be executed
    # @param accessToken         This is the access_token value received from the 
    #                            login response
    # @param instanceUrl         This is the instance_url value received from the 
    #                            login response
    ##
    def query(queryString, accessToken, instanceUrl):
        queryUri = '/query/?q='
        headerDetails = {'Authorization': 'Bearer ' + accessToken,'X-PrettyPrint':1}
        urlEncodedQuery = urllib.parse.quote(queryString)

        response = WebService.Tools.getHTResponse(instanceUrl + Tooling.baseToolingUri + queryUri + urlEncodedQuery, headerDetails)
        jsonResponse = json.loads(response.text)

        return jsonResponse

    ##
    # This method runs the tests provided with the class Ids, then returns the 
    # direct results from the Salesforce tooling API.
    #
    # @param classIds           List of comma separated class Ids to run the tests
    # @param accessToken        This is the access_token value received from the 
    #                           login response
    # @param instanceUrl        This is the instance_url value received from the 
    #                           login response
    ##
    # def runTestsAsynchronous(classIds, accessToken, instanceUrl):
    #     testAsyncUri = '/runTestsAsynchronous/?classids='
    #     headerDetails = {'Authorization': 'Bearer ' + accessToken,'X-PrettyPrint':1}
    #     urlEncodedClassIds = urllib.parse.quote(classIds)

    #     response = WebService.Tools.getHTResponse(instanceUrl + Tooling.baseToolingUri + testAsyncUri + urlEncodedClassIds, headerDetails)
    #     jsonResponse = json.loads(response.text)

    #     return jsonResponse

    def runTestsAsynchronousList(classIds, accessToken, instanceUrl):
        testAsyncUri = '/runTestsAsynchronous/'
        headerDetails = {'Authorization': 'Bearer ' + accessToken,'X-PrettyPrint':1}
        urlEncodedClassIds = urllib.parse.quote(classIds)

        response = WebService.Tools.postHTResponse(instanceUrl + Tooling.baseToolingUri + testAsyncUri + urlEncodedClassIds, classIds, headerDetails)
        jsonResponse = json.loads(response.text)

        return jsonResponse