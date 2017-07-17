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
    # @param headerDetails   Object containing the headers for the request. 
    #						 Defaults to None
    # @param dataBody        The body to send for the POST. Defaults to None
    # @return 				 Returns the response for the HTTP Request.
    ##
    def http_request(**kwargs):
        requestType = kwargs.get('requestType')
        URL = kwargs.get('URL')
        headerDetails = kwargs.get('headerDetails', None)
        dataBody = kwargs.get('dataBody', None)

        response = ""

        try:
            req = requests.Request(requestType, URL, data=dataBody, headers=headerDetails)
            prepReq = req.prepare()
            session = requests.Session()
            session.mount('https://', SslHttpAdapter())
            response = session.send(prepReq)
        except:
            errors = "";
            
            for e in sys.exc_info():
                errors += " " + repr(e)
            
            print("Errors with response from {}: {}".format(str(URL), errors))
            sys.exit(68) # code: host name unknown
        
        return response


    ##
    # This returns the response from an HTTP GET request
    #
    # @param URL             The full URL to call
    # @param headerDetails   Object containing the headers for the request
    # @return                Returns the result of the HTTP GET request.
    ##
    def get_http_response(URL, headerDetails):
        response = Tools.http_request(requestType='GET', URL=URL, headerDetails=headerDetails)
        
        return response

    ##
    # This returns the response from an HTTP POST request
    #
    # @param URL             The full URL to call
    # @param dataBody        The body to send for the POST
    # @param headerDetails   Object containing the headers for the request
    # @return                Returns the result of the HTTP POST request.
    ##
    def post_http_response(URL, dataBody, headerDetails):
        response = Tools.http_request(requestType='POST', URL=URL, dataBody=dataBody, headerDetails=headerDetails)

        return response

    ##
    # This returns the response from an HTTP POST request
    #
    # @param URL             The full URL to call
    # @param dataBody        The body to send for the POST
    # @param headerDetails   Object containing the headers for the request
    # @return                Returns the result of the HTTP POST request.
    ##
    def patch_http_response(URL, dataBody, headerDetails):
        response = Tools.http_request(requestType='PATCH', URL=URL, dataBody=dataBody, headerDetails=headerDetails)

        return response

class SslHttpAdapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = requests.packages.urllib3.poolmanager.PoolManager(
                                num_pools=connections, maxsize=maxsize,
                                block=block, ssl_version=ssl.PROTOCOL_SSLv23)