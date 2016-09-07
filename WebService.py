#!/usr/local/Cellar/python3/3.5.2_1/bin
import requests
import sys
import ssl

class Tools:
	def getHTResponse(URL, headerDetails):

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
			
			print ("Unable to reach " + str(URL) + ": " + errors)
			sys.exit(68) # code: host name unknown

		return response

class sslHttpAdapter(requests.adapters.HTTPAdapter):
	def init_poolmanager(self, connections, maxsize, block=False):
		print("setting ssl")
		self.poolmanager = requests.packages.urllib3.poolmanager.PoolManager(
								num_pools=connections, maxsize=maxsize,
								block=block, ssl_version=ssl.PROTOCOL_SSLv23)