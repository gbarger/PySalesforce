#!/usr/bin/python3
import requests
import sys
import ssl

class Tools:
    def getHTResponse(URL, headerDetails):
        response = ""

        try:
            req = requests.Request('GET', URL, headers=headerDetails)
            prepReq = req.prepare()
            session = requests.Session()
            session.mount('https://', sslHttpAdapter())
            response = session.send(prepReq)
        except:
            errors = "";
            
            for e in sys.exc_info():
                errors += " " + repr(e)
            
            print ("Unable to reach " + str(URL) + ": " + errors)
            sys.exit(68) # code: host name unknown
        
        return response

    def postHTResponse(URL, dataBody, headerDetails):
        response = ""

        try:
            req = requests.Request('POST', URL, data=dataBody, headers=headerDetails)
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

    def patchHTResponse(URL, dataBody, headerDetails):
    	response = ""

    	return response

class sslHttpAdapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = requests.packages.urllib3.poolmanager.PoolManager(
                                num_pools=connections, maxsize=maxsize,
                                block=block, ssl_version=ssl.PROTOCOL_SSLv23)