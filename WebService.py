#!usr/bin/python
import requests
import json
import sys
import codecs

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

	def getJSONResponse(URL):
		try:
			htResponse = Tools.getHTResponse(URL, '')
			response = json.loads(htResponse.text)
		except:
			errors = ""

			for e in sys.exc_info():
				errors += " " + repr(e)

			print("Unable to parse json for " + str(URL) + ": " + errors)
			sys.exit(68)

		print("Parsed response to JSON.")
		return response

	def getJSONResponseFile(inputFile):
		print("Opening input file.")

		try:
			fileData = open(inputFile, "r").read()
			response = json.loads(fileData)
		except:
			errors = ""

			for e in sys.exc_info():
				errors += " " + repr(e)

			print("Unable to parse json for " + str(inputFile) + ": " + errors)
			sys.exit(68)

		print("Input file opened.")
		print("Parsed input file to JSON.")
		return response

class ToCSV:
	def writeHeaders(writeFile, headerArray):
		print("Writing file headers")

		for i in range(0, len(headerArray)):
			writeFile.write('"' + headerArray[i] + '"')

			if i < len(headerArray) - 1:
				writeFile.write(',')

		print("File headers written.")

	def writeRecords(writeFile, varNames, inputData):
		print("Writing file records.")
		
		for row in inputData:
			writeFile.write('\n')

			for i in range(0, len(varNames)):
				value = row[varNames[i]]

				if value is None:
					writeFile.write('""')
				else:
					#value = unicode(value) # unicode for python 2
					value = str(value) # str for python 3
					writeFile.write('"' + value + '"')

				if i < len(varNames) - 1:
					writeFile.write(',')

		print("File write process complete.")