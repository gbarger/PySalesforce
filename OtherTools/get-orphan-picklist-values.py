#!usr/bin/python

#TODO:
# Add connection to authenitcate and pull the object so it doesn't need to be done manually

import requests
import sys
import xml.etree.ElementTree as ET
import urllib.parse

nsString = './/{http://soap.sforce.com/2006/04/metadata}'
fieldsElement = nsString + 'fields'
fullNameElement = nsString + 'fullName'
picklistElement = nsString + 'picklist'
controllingFieldElement = nsString + 'controllingField'
picklistValuesElement = nsString + 'picklistValues'
valuesElement = nsString + 'values'
recordTypesElement = nsString + 'recordTypes'
controllingFieldValuesElement = nsString + 'controllingFieldValues'

def main():
    i = 0
    for i in range(0, len(sys.argv)):
        arg = sys.argv[i]

        if arg == '-username':
            i += 1
            username = sys.argv[i]
        elif arg == '-password':
            i += 1
            password = sys.argv[i]
        elif arg == '-isTest':
            i += 1
            isTest = sys.argv[i]
        elif arg == '-infile':
            i += 1
            filename = sys.argv[i]
        elif arg == '-outfile':
            i += 1
            outfile = sys.argv[i]
        elif arg == '-field':
            i += 1
            fieldToGet = sys.argv[i]

    non_used_dependency_values = set()
    allValues = set()
    record_type_used_values = set()

    tree = ET.parse(filename)
    root = tree.getroot()

    # get list of orphaned picklist values baed on picklist dependency
    for field in root.findall(fieldsElement):
        try:
            name = field.find(fullNameElement).text

            if name == fieldToGet:
                picklist = field.find(picklistElement)

                controllingField = picklist.find(controllingFieldElement)

                for picklistValue in picklist.findall(picklistValuesElement):
                    picklistName = picklistValue.find(fullNameElement).text
                    allValues.add(picklistName)

                    controllingElements = picklistValue.findall(controllingFieldValuesElement)

                    if controllingField is None:
                        continue

                    if len(controllingElements) == 0:
                        non_used_dependency_values.add(picklistName)

                break
        except:
            # do nothing to catch
            print("")

    # get list of all picklist values referenced across record types
    for recordType in root.findall(recordTypesElement):
        rtName = recordType.find(fullNameElement).text

        for picklistValue in recordType.findall(picklistValuesElement):
            picklistName = picklistValue.find(picklistElement).text

            if picklistName == fieldToGet:
                for value in picklistValue.findall(valuesElement):
                    valueName = urllib.parse.unquote(value.find(fullNameElement).text)

                    record_type_used_values.add(valueName)

                break

    non_used_recordtype_values = allValues.difference(record_type_used_values)
    all_non_used_picklist_values = non_used_dependency_values.union(non_used_recordtype_values)

    if len(all_non_used_picklist_values) > 0:
        sortedList = sorted(all_non_used_picklist_values, key=lambda item: (int(item.partition(' ')[0])
                            if item[0].isdigit() else float('inf'), item))

        for value in sortedList:
            print(value)

    non_used_count = len(all_non_used_picklist_values)
    all_count = len(allValues)
    print("\norphaned picklist values for {}: {} out of {}".format(fieldToGet, non_used_count, all_count))


if __name__ == "__main__":
    main()
