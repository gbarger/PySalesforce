#!/usr/bin/python3
import httpx
import sys

class Tools:
    # seconds to wait for the server to connect or send data. Set to None to
    # wait forever.
    default_timeout = 120

    # all requests share this client so connections to the same host are
    # reused, which avoids a new TLS handshake for every request.
    client = httpx.Client(follow_redirects=True)

    @staticmethod
    def http_request(**kwargs):
        """
        This method is the generic method used for creating HTTP requests.
        
        Args:
            requestType (str): The request type: GET, POST, PATCH, DELETE, etc
            URL (str): The full URL to call
            header_details (dict): Object containing the headers for the request. 
                                  Defaults to None
            data_body (dict): The body to send for the POST. A dict is sent
                              as form fields, and a str or bytes value is
                              sent as is. Defaults to None
            files (dict): The parts of a multipart message. Defaults to None

        Returns:
            httpx.Response: Returns the response for the HTTP Request.
        """
        requestType = kwargs.get('requestType')
        URL = kwargs.get('URL')
        header_details = kwargs.get('header_details', None)
        data_body = kwargs.get('data_body', None)
        files = None
        if 'files' in kwargs:
            files = kwargs.get('files', None)

        response = ""

        # never send the access token over an unencrypted connection
        if header_details and 'Authorization' in header_details and not URL.lower().startswith('https://'):
            raise ValueError('The access token can only be sent to an https URL: {}'.format(URL))

        # a dict is sent as form fields, anything else is sent as it is
        body_arguments = {}

        if isinstance(data_body, dict):
            body_arguments['data'] = data_body
        elif data_body is not None:
            body_arguments['content'] = data_body

        try:
            response = Tools.client.request(requestType, URL, headers=header_details or None, files=files,
                                            timeout=Tools.default_timeout, **body_arguments)

            # only 4xx and 5xx are errors. 304 Not Modified is a normal response
            if response.is_error:
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            # the response body won't be visible if exception is just raised
            try:
                error_body = e.response.json()
            except ValueError:
                error_body = e.response.text

            new_error_str = '{} response: {}' .format(str(e), str(error_body))
            raise httpx.HTTPStatusError(new_error_str, request=e.request,
                                        response=e.response).with_traceback(sys.exc_info()[2])
        return response

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def post_http_response(URL, data_body, header_details, files=None):
        """
        This returns the response from an HTTP POST request

        Args:
            URL (str): The full URL to call
            data_body (str): The body to send for the POST
            header_details (dict): Object containing the headers for the request
            files: attached files/Multipart message

        Returns:
            dict: Returns the result of the HTTP POST request.
        """
        response = Tools.http_request(requestType='POST', URL=URL, data_body=data_body, header_details=header_details,
                                      files=files)

        return response

    @staticmethod
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

    @staticmethod
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
