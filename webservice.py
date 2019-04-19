#!/usr/bin/python3
import requests
import sys
import ssl

from urllib3.poolmanager import PoolManager

class Tools:


    def http_request(**kwargs):
        """
        This method is the generic method used for creating HTTP requests.
        
        Args:
            requestType (str): The request type: GET, POST, PATCH, DELETE, etc
            URL (str): The full URL to call
            header_details (dict): Object containing the headers for the request. 
                                  Defaults to None
            data_body (dict): The body to send for the POST. Defaults to None

        Returns:
            dict: Returns the response for the HTTP Request.
        """
        requestType = kwargs.get('requestType')
        URL = kwargs.get('URL')
        header_details = kwargs.get('header_details', None)
        data_body = kwargs.get('data_body', None)

        response = ""

        try:
            req = requests.Request(requestType, URL, data=data_body, headers=header_details)
            prepReq = req.prepare()
            session = requests.Session()
            session.mount('https://', SslHttpAdapter())
            response = session.send(prepReq)
        except:
            errors = ""

            for e in sys.exc_info():
                errors += " " + repr(e)

            print("Errors with response from {}: {}".format(str(URL), errors))
            sys.exit(68) # code: host name unknown

        return response


    def get_http_response(URL, header_details):
        """
        This returns the response from an HTTP GET request

        Args:
            URL (str): The full URL to call
            header_details (dict): Object containing the headers for the request

        Returns:
            dict: Returns the result of the HTTP GET request.
        """
        response = Tools.http_request(requestType='GET', URL=URL, header_details=header_details)

        return response


    def put_http_response(URL, data_body, header_details):
        """
        This returns the response from an HTTP PUT request

        Args:
            URL (str): The full URL to call
            data_body (str): The body to send for the PUT
            header_details (dict): Object containing the headers for the request

        Returns:
            dict: Returns the result of the HTTP PUT request.
        """
        response = Tools.http_request(requestType='PUT', URL=URL, data_body=data_body, header_details=header_details)

        return response


    def post_http_response(URL, data_body, header_details):
        """
        This returns the response from an HTTP POST request

        Args:
            URL (str): The full URL to call
            data_body (str): The body to send for the POST
            header_details (dict): Object containing the headers for the request

        Returns:
            dict: Returns the result of the HTTP POST request.
        """
        response = Tools.http_request(requestType='POST', URL=URL, data_body=data_body, header_details=header_details)

        return response


    def patch_http_response(URL, data_body, header_details):
        """
        This returns the response from an HTTP POST request

        Args:
            URL (str): The full URL to call
            data_body (str): The body to send for the POST
            header_details (dict): Object containing the headers for the request
        
        Returns:
            dict: Returns the result of the HTTP POST request.
        """
        response = Tools.http_request(requestType='PATCH', URL=URL, data_body=data_body, header_details=header_details)

        return response


    def delete_http_response(URL, data_body, header_details):
        """
        This returns the response from an HTTP DELETE request

        Args:
            URL (str): The full URL to call
            data_body (str): The body to send for the DELETE
            header_details (dict): Object containing the headers for the request
        
        Returns:
            dict: Returns the result of the HTTP DELETE request.
        """
        response = Tools.http_request(requestType='DELETE', URL=URL, data_body=data_body, header_details=header_details)

        return response


class SslHttpAdapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(
                                num_pools=connections, maxsize=maxsize,
                                block=block, ssl_version=ssl.PROTOCOL_SSLv23)