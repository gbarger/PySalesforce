#!usr/bin/python
import requests
import sys
from requests.adapters import HTTPAdapter
import urllib3
from requests.packages.urllib3.poolmanager import PoolManager
import ssl


### start import for logging
import logging
import http.client as http_client
### end import for logging

class Tools:
	def getHTResponse(URL, headerDetails):
		print("\nPrinting GET details:")
		print("URL: {}".format(URL))
		print("header: {}\n".format(headerDetails))

		try:
			req = requests.Request('GET', URL, headers=headerDetails)
			prepReq = req.prepare()
			session = requests.Session()
			session.mount('https://', sslHttpAdapter())
			response = session.send(prepReq)

			# Tools.printResponse(response)
		except:
			errors = "";
			
			for e in sys.exc_info():
				errors += " " + repr(e)
			
			print ("Unable to reach " + str(URL) + ": " + errors)
			sys.exit(68) # code: host name unknown
		
		return response

	def postHTResponse(URL, dataBody, headerDetails):
		print("\nPrinting POST details:")
		print("URL: {}".format(URL))
		print("header: {}".format(headerDetails))
		print("body: {}\n".format(dataBody))

		######### start of logging
		try:
		    import http.client as http_client
		except ImportError:
		    # Python 2
		    import httplib as http_client
		http_client.HTTPConnection.debuglevel = 1

		logging.basicConfig()
		logging.getLogger().setLevel(logging.DEBUG)
		requests_log = logging.getLogger("requests.packages.urllib3")
		requests_log.setLevel(logging.DEBUG)
		requests_log.propagate = True
		######### end of logging

		try:
			# req = requests.Request('POST', URL, data=dataBody, headers=headerDetails)
			# prepReq = req.prepare()
			# session = requests.Session()
			# session.mount('https://', sslHttpAdapter())
			# response = session.send(prepReq)

			httpr = urllib3.PoolManager()
			response = httpr.request('POST', URL, fields=dataBody)

			print("\n\n\nresponse status: {0}\nresponse headers: {1}\nresponse data: {2}\n\n\n".format(response.status, response.headers, response.data))

			# Tools.printResponse(response)
		except:
			errors = "";
			
			for e in sys.exc_info():
				errors += " " + repr(e)
			
			print ("Unable to reach " + str(URL) + ": " + errors)
			sys.exit(68) # code: host name unknown

		return response

	def printResponse(response):
		print("\nresponse details:")
		print("\ncontent: {}".format(response.content))
		print("\ncookies: {}".format(response.cookies))
		print("\nencoding: {}".format(response.encoding))
		print("\nheaders: {}".format(response.headers))
		print("\nhistory: {}".format(response.history))
		print("\nrequest: {}".format(response.request))
		print("\nstatus_code: {}".format(response.status_code))
		print("\ntext: {}".format(response.text))
		print("\nurl: {}".format(response.url))

class sslHttpAdapter(HTTPAdapter):
	def init_poolmanager(self, connections, maxsize, block=False):
		self.poolmanager = PoolManager(num_pools=connections, maxsize=maxsize,
										block=block, ssl_version=ssl.PROTOCOL_SSLv23) # PROTOCOL_TLSv1_2 PROTOCOL_SSLv23 PROTOCOL_TLSv1 NO_SSL_
