#!/usr/bin/python3
import requests
import sys
import ssl

class Tools:
    ##
    # This method is the generic method used for creating HTTP requests.
    #
    # @param requestType     The request type: GET, POST, PATCH, DELETE, etc
    # @param URL             The full URL to call
    # @param headerDetails   Object containing the headers for the request
    # @param dataBody        The body to send for the POST
    # @return 				 Returns the response for the HTTP Request.
    ##
    def htRequest(**kwargs):
        requestType = kwargs.get('requestType')
        URL = kwargs.get('URL')
        headerDetails = kwargs.get('headerDetails', None)
        dataBody = kwargs.get('dataBody', None)

        response = ""

        try:
            req = requests.Request(requestType, URL, data=dataBody, headers=headerDetails)
            prepReq = req.prepare()
            session = requests.Session()
            session.mount('https://', sslHttpAdapter())
            response = session.send(prepReq)
        except:
            errors = "";
            
            for e in sys.exc_info():
                errors += " " + repr(e)
            
            print ("Errors with response from {}: {}".format(str(URL), errors))
            sys.exit(68) # code: host name unknown
        
        return response


    ##
    # This returns the response from an HTTP GET request
    #
    # @param URL             The full URL to call
    # @param headerDetails   Object containing the headers for the request
    # @return                Returns the result of the HTTP GET request.
    ##
    def getHTResponse(URL, headerDetails):
        response = Tools.htRequest(requestType='GET', URL=URL, headerDetails=headerDetails)
        
        return response

    ##
    # This returns the response from an HTTP POST request
    #
    # @param URL             The full URL to call
    # @param dataBody        The body to send for the POST
    # @param headerDetails   Object containing the headers for the request
    # @return                Returns the result of the HTTP POST request.
    ##
    def postHTResponse(URL, dataBody, headerDetails):
        response = Tools.htRequest(requestType='POST', URL=URL, dataBody=dataBody, headerDetails=headerDetails)

        return response

    ##
    # This returns the response from an HTTP POST request
    #
    # @param URL             The full URL to call
    # @param dataBody        The body to send for the POST
    # @param headerDetails   Object containing the headers for the request
    # @return                Returns the result of the HTTP POST request.
    ##
    def patchHTResponse(URL, dataBody, headerDetails):
        response = Tools.htRequest(requestType='PATCH', URL=URL, dataBody=dataBody, headerDetails=headerDetails)

        return response

class sslHttpAdapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = requests.packages.urllib3.poolmanager.PoolManager(
                                num_pools=connections, maxsize=maxsize,
                                block=block, ssl_version=ssl.PROTOCOL_SSLv23)