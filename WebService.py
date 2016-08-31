#!usr/bin/python
import requests
import sys

class Tools:
	def getHTResponse(URL, headerDetails):
		print("\nPrinting GET details:")
		print("URL: {}".format(URL))
		print("header: {}\n".format(headerDetails))

		try:
			req = requests.Request('GET', URL, headers=headerDetails)
			prepReq = req.prepare()
			session = requests.Session()
			response = session.send(prepReq)
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

		try:
			req = requests.Request('POST', URL, data=dataBody, headers=headerDetails)
			prepReq = req.prepare()
			session = requests.Session()
			response = session.send(prepReq)
		except:
			errors = "";
			
			for e in sys.exc_info():
				errors += " " + repr(e)
			
			print ("Unable to reach " + str(URL) + ": " + errors)
			sys.exit(68) # code: host name unknown

		return response