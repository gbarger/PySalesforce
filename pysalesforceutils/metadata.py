#!/usr/bin/python3

"""
Salesforce Metadata API.
"""

import pysalesforceutils
from .util import Util


class Metadata:
    """
    Use Metadata API to retrieve, deploy, create, update or delete customization
    information, such as custom object definitions and page layouts, for your
    organization. This API is intended for managing customizations and for
    building tools that can manage the metadata model, not the data itself.
    """

    @staticmethod
    def get_session_header(session_id):
        """
        Used to get the session header for the given session_id

        Args:
            session_id (str): The session ID that the login call returns.

        Returns:
            object: Returns the session header element for SOAP Metadata
                    requests
        """
        client = Util.get_soap_client(pysalesforceutils.METADATA_WSDL_FILE)
        session_header_element = client.get_element('ns0:SessionHeader')
        session_header = session_header_element(session_id)

        return session_header

    @staticmethod
    def get_call_options(client_name):
        """
        This returns the call options for the soap header

        Args:
            client_name     A value that identifies an API client.

        Returns:
            object: Returns the call options element for SOAP Metadata requests
        """
        client = Util.get_soap_client(pysalesforceutils.METADATA_WSDL_FILE)
        call_options_element = client.get_element('ns0:CallOptions')
        call_options = call_options_element(client_name)

        return call_options

    @staticmethod
    def get_all_or_none_header(all_or_none):
        """
        Indicates whether to roll back all metadata changes when some of the
        records in a call result in failures.

        Args:
            all_or_none (bool): Set to true to cause all metadata changes to be
                                rolled back if any records in the call cause
                                failures. Set to false to enable saving only the
                                records that are processed successfully when
                                other records in the call cause failures.

        Returns:
            object: Returns the AllOrNoneHeader element for SOAP Metadata
                    requests
        """
        client = Util.get_soap_client(pysalesforceutils.METADATA_WSDL_FILE)
        all_or_none_header_element = client.get_element('ns0:AllOrNoneHeader')
        all_or_none_header = all_or_none_header_element(all_or_none)

        return all_or_none_header

    @staticmethod
    def get_debugging_header(categories):
        """
        Specifies that the deployment result will contain the debug log output,
        and specifies the level of detail included in the log. The debug log
        contains the output of Apex tests that are executed as part of a
        deployment.

        Args:
            categories (array): A list of log categories with their associated
                                log levels.

        Returns:
            object: Returns the DebuggingHeader for SOAP Metadata requests
        """
        client = Util.get_soap_client(pysalesforceutils.METADATA_WSDL_FILE)
        debugging_header_element = client.get_element('ns0:DebuggingHeader')
        debugging_header = debugging_header_element(categories, None)

        return debugging_header

    @staticmethod
    def get_soap_headers(session_id, client_name, all_or_none, debug_categories):
        """
        This builds the session header for the Metadata requests

        Args:
            session_id (str): The session ID that the login call returns.
            client_name (str): A value that identifies an API client.
            all_or_none (bool): Set to true to cause all metadata changes to be
                                rolled back if any records in the call cause
                                failures. Set to false to enable saving only the
                                records that are processed successfully when
                                other records in the call cause failures.
            debug_categories (array): A list of log categories with their
                                      associated log levels.

        Returns:
            object: Returns the headers for SOAP Metadata requests
        """
        soap_headers = {}
        soap_headers['SessionHeader'] = Metadata.get_session_header(session_id)

        if client_name != None:
            soap_headers['CallOptions'] = Metadata.get_call_options(client_name)

        if all_or_none != None:
            soap_headers['AllOrNoneHeader'] = Metadata.get_all_or_none_header(all_or_none)

        if debug_categories != None:
            soap_headers['DebuggingHeader'] = Metadata.get_debugging_header(debug_categories)

        return soap_headers

    @staticmethod
    def get_metadata(full_name):
        """
        This is the base class for all metadata types. You cannot edit this
        object. A component is an instance of a metadata type.
        Metadata is analogous to sObject, which represents all standard objects.
        Metadata represents all components and fields in Metadata API. Instead
        of identifying each component with an ID, each custom object or custom
        field has a unique fullName, which must be distinct from standard object
        names, as it must be when you create custom objects or custom fields in
        the Salesforce user interface.

        Args:
            full_name (str): Required. The name of the component. If a field,
                             the name must specify the parent object, for
                             example Account.FirstName. The __c suffix must be
                             appended to custom object names and custom field
                             names when you are setting the fullName. For
                             example, a custom field in a custom object could
                             have a fullName of MyCustomObject__c.MyCustomField__c.
                             To reference a component in a package, prepend the
                             package’s namespace prefix to the component name in
                             the fullName field. Use the following syntax:
                             namespacePrefix__ComponentName. For example, for the
                             custom field component MyCustomObject__c.MyCustomField__c
                             and the namespace MyNS, the full name is
                             MyNS__MyCustomObject__c.MyCustomField__c.

        Returns:
            object: Returns the metadata object
        """
        client = Util.get_soap_client(pysalesforceutils.METADATA_WSDL_FILE)
        metadata_type = client.get_type('ns0:Metadata')
        metadata = metadata_type(full_name)

        return metadata

    @staticmethod
    def get_package_type_members(member_name, member_list):
        """
        This builds the list of members for a specific type. For example this
        will store the list of all the ApexClass members you want to reference.

        Args:
            member_name (str): This is the Metadata type being referenced.
                               A list of types can be found here: https://
                               developer.salesforce.com/docs/atlas.en-us.
                               api_meta.meta/api_meta/meta_types_list.htm
            member_list (array): An array of the members you're working with in
                                 the package.

        Returns:
            object: Returns the package type members for making SOAP Metadata
                    requests
        """
        package_type_members = {}
        package_type_members['name'] = member_name
        package_type_members['members'] = member_list

        return package_type_members

    @staticmethod
    def get_client_service(metadata_url):
        """
        This method builds the client service for the Metadata API

        Args:
            metadata_url (str): The Url used to send this request to

        Returns:
            Returns the client service for SOAP Metadata requests
        """
        if not metadata_url.lower().startswith('https://'):
            raise ValueError('The session id can only be sent to an https URL: {}'.format(metadata_url))

        soap_client_service = Util.get_soap_client_service(pysalesforceutils.METADATA_WSDL_FILE, pysalesforceutils.METADATA_SERVICE_BINDING, metadata_url)

        return soap_client_service

    @staticmethod
    def get_package(**kwargs):
        """
        Specifies which metadata components to retrieve as part of a retrieve()
        call or defines a package of components.

        Args:
            full_name (str): The package name used as a unique identifier for
                             API access. The fullName can contain only
                             underscores and alphanumeric characters. It must be
                             unique, begin with a letter, not include spaces,
                             not end with an underscore, and not contain two
                             consecutive underscores. This field is inherited
                             from the Metadata component.
            api_access_level (str): Package components have access via dynamic
                                    Apex and the API to standard and custom
                                    objects in the organization where they are
                                    installed. Administrators who install
                                    packages may wish to restrict this access
                                    after installation for improved security.
                                    The valid values are:
                                    * Unrestricted—Package components have
                                        the same API access to standard objects
                                        as the user who is logged in when the
                                        component sends a request to the API.
                                    * Restricted—The administrator can select
                                        which standard objects the components
                                        can access. Further, the components in
                                        restricted packages can only access
                                        custom objects in the current package
                                        if the user's permissions allow access
                                        to them.
                                    For more information, see “About API and
                                    Dynamic Apex Access in Packages” in the
                                    Salesforce online help.
            description (str): A short description of the package.
            namespace_prefix (str): The namespace of the developer organization
                                     where the package was created.
            object_permissions (array): Indicates which objects are accessible to
                                        the package, and the kind of access
                                        available (create, read, update, delete)
            package_type (str): Reserved for future use.
            post_install_class (str): The name of the Apex class that specifies
                                      the actions to execute after the package
                                      has been installed or upgraded. The Apex
                                      class must be a member of the package and
                                      must implement the Apex InstallHandler
                                      interface. In patch upgrades, you can't
                                      change the class name in this field but
                                      you can change the contents of the Apex
                                      class. The class name can be changed in
                                      major upgrades. This field is available in
                                      API version 24.0 and later.
            setup_web_link (str): The weblink used to describe package
                                  installation.
            types (array): The type of component being retrieved. You can build
                           the types with the get_package_type_members() method.
            uninstall_class (str): The name of the Apex class that specifies
                                   the actions to execute after the package has
                                   been uninstalled. The Apex class must be a
                                   member of the package and must implement the
                                   Apex UninstallHandler interface. In patch
                                   upgrades, you can't change the class name in
                                   this field but you can change the contents of
                                   the Apex class. The class name can be changed
                                   in major upgrades.
                                   This field is available in API version 25.0
                                   and later.
            version (str): Required. The version of the component type.

        Returns:
            object: Returns the package that was requested.
        """
        if kwargs.get('version') is None:
            raise ValueError('The version parameter is required to create a package.')

        client = Util.get_soap_client(pysalesforceutils.METADATA_WSDL_FILE)
        package_type = client.get_type('ns0:Package')
        this_package = package_type(
            kwargs.get('full_name'),
            kwargs.get('api_access_level'),
            kwargs.get('description'),
            kwargs.get('namespace_prefix'),
            kwargs.get('object_permissions'),
            kwargs.get('package_type'),
            kwargs.get('post_install_class'),
            kwargs.get('setup_web_link'),
            kwargs.get('types'),
            kwargs.get('uninstall_class'),
            kwargs.get('version')
        )

        return this_package

    @staticmethod
    def get_deploy_options(**kwargs):
        """
        The options that can be set for deploying a metadata package

        Args:
            allow_missing_files (bool): If files that are specified in package.xml
                                        are not in the .zip file, specifies whether
                                        a deployment can still succeed.
                                        Do not set this argument for deployment to
                                        production orgs.
            auto_update_package (bool): If a file is in the .zip file but not
                                        specified in package.xml, specifies whether
                                        the file is automatically added to the
                                        package. A retrieve() is issued with the
                                        updated package.xml that includes the .zip
                                        file.
                                        Do not set this argument for deployment to
                                        production orgs.
            check_only (bool): Defaults to false. Set to true to perform a
                               test deployment (validation) of components
                               without saving the components in the target
                               org. A validation enables you to verify the
                               results of tests that would be generated in
                               a deployment, but doesn’t commit any changes.
                               After a validation finishes with passing tests,
                               it might qualify for deployment without
                               rerunning tests. See deployRecentValidation().
            ignore_warnings (bool): Indicates whether a warning should allow a
                                    deployment to complete successfully (true)
                                    or not (false). Defaults to false.
                                    The DeployMessage object for a warning
                                    contains the following values:
                                        -problemType—Warning
                                        -problem—The text of the warning.
                                    If a warning occurs and ignoreWarnings is
                                    set to true, the success field in
                                    DeployMessage is true. If ignoreWarnings is
                                    set to false, success is set to false and
                                    the warning is treated like an error.
            perform_retrieve (bool): Indicates whether a retrieve() call is
                                     performed immediately after the deployment
                                     (true) or not (false). Set to true in order
                                     to retrieve whatever was just deployed.
            purge_on_delete (bool): If true, the deleted components in the
                                    destructiveChanges.xml manifest file aren't
                                    stored in the Recycle Bin. Instead, they
                                    become immediately eligible for deletion.
                                    This option only works in Developer Edition
                                    or sandbox orgs; it doesn't work in
                                    production orgs.
            rollback_on_error (bool): Indicates whether any failure causes a
                                      complete rollback (true) or not (false). If
                                      false, whatever actions can be performed
                                      without errors are performed, and errors are
                                      returned for the remaining actions. This
                                      parameter must be set to true if you are
                                      deploying to a production org. The default
                                      is false.
            run_tests (array): A list of Apex tests to run during
                               deployment. Specify the class name, one name
                               per instance. The class name can also
                               specify a namespace with a dot notation. For
                               more information, see Running a Subset of
                               Tests in a Deployment.
                               To use this option, set testLevel to
                               RunSpecifiedTests.
            single_package (bool): Indicates whether the specified .zip file
                                   points to a directory structure with a
                                   single package (true) or a set of packages
                                   (false).
            test_level (str): Optional. Specifies which tests are run as
                              part of a deployment. The test level is
                              enforced regardless of the types of
                              components that are present in the deployment
                              package. Valid values are:
                                  -NoTestRun—No tests are run. This test
                                  level applies only to deployments to
                                  development environments, such as
                                  sandbox, Developer Edition, or trial
                                  organizations. This test level is the
                                  default for development environments.
                                  -RunSpecifiedTests—Only the tests that
                                  you specify in the runTests option are
                                  run. Code coverage requirements differ
                                  from the default coverage requirements
                                  when using this test level. Each class
                                  and trigger in the deployment package
                                  must be covered by the executed tests
                                  for a minimum of 75% code coverage.
                                  This coverage is computed for each
                                  class and trigger individually and is
                                  different than the overall coverage
                                  percentage.
                                  -RunLocalTests—All tests in your org are
                                  run, except the ones that originate
                                  from installed managed packages. This
                                  test level is the default for production
                                  deployments that include Apex classes
                                  or triggers.
                                  -RunAllTestsInOrg—All tests are run. The
                                  tests include all tests in your org,
                                  including tests of managed packages.

        Returns:
            object: Returns the deploy options object for creating SOAP Metadata
                    requests
        """
        client = Util.get_soap_client(pysalesforceutils.METADATA_WSDL_FILE)
        deploy_options_type = client.get_type('ns0:DeployOptions')
        deploy_options = deploy_options_type(
            kwargs.get('allow_missing_files'),
            kwargs.get('auto_update_package'),
            kwargs.get('check_only'),
            kwargs.get('ignore_warnings'),
            kwargs.get('perform_retrieve'),
            kwargs.get('purge_on_delete'),
            kwargs.get('rollback_on_error'),
            kwargs.get('run_tests'),
            kwargs.get('single_package'),
            kwargs.get('test_level')
        )

        return deploy_options

    @staticmethod
    def get_retrieve_request(**kwargs):
        """
        This is the package of data needed to retrieve metadata

        Args:
            api_version (dbl): Required. The API version for the retrieve
                               request. The API version determines the fields
                               retrieved for each metadata type. For example,
                               an icon field was added to the CustomTab for
                               API version 14.0. If you retrieve components
                               for version 13.0 or earlier, the components
                               will not include the icon field.
            package_names (array): A list of package names to be retrieved. If
                                   you are retrieving only unpackaged components,
                                   do not specify a name here. You can retrieve
                                   packaged and unpackaged components in the
                                   same retrieve.
            single_package (bool): Specifies whether only a single package is
                                   being retrieved (true) or not (false). If
                                   false, then more than one package is being
                                   retrieved.
            specific_files (array): A list of file names to be retrieved. If a
                                    value is specified for this property,
                                    package_names must be set to null and
                                    single_package must be set to true.
            unpackaged (array): A list of components to retrieve that are not
                                in a package. You can build the package using
                                the get_package() method.

        Returns:
            object: Returns the retrieve request used to create SOAP Metadata
                    requests
        """
        if kwargs.get('api_version') is None:
            raise ValueError('The api_version parameter is required to create a retrieve request.')

        client = Util.get_soap_client(pysalesforceutils.METADATA_WSDL_FILE)
        retrieveRequest_type = client.get_type('ns0:RetrieveRequest')
        this_retrieve_request = retrieveRequest_type(
            kwargs.get('api_version'),
            kwargs.get('package_names'),
            kwargs.get('single_package'),
            kwargs.get('specific_files'),
            kwargs.get('unpackaged')
        )

        return this_retrieve_request

    @staticmethod
    def get_list_metadata_query(folder, metadata_type):
        client = Util.get_soap_client(pysalesforceutils.METADATA_WSDL_FILE)
        list_metadata_query_type = client.get_type('ns0:ListMetadataQuery')
        metadata_query = list_metadata_query_type(folder, metadata_type)

        return metadata_query

    @staticmethod
    def retrieve(retrieve_request, session_id, metadata_url, client_name):
        """
        This returns the async result of a retrieve request that can then be
        used to check the retrieve status

        Args:
            retrieve_request (object): The request settings which can be created
                                       using the get_retrieve_request() method
            session_id (str): The session ID that the login call returns.
            metadata_url (str): The Url used to send this request to
            client_name (str): A value that identifies an API client. This is
                               used for partner applications
        """
        soap_headers = Metadata.get_soap_headers(session_id, client_name, None, None)

        client_service = Metadata.get_client_service(metadata_url)
        this_retrieve = client_service.retrieve(retrieve_request, _soapheaders=soap_headers)

        return this_retrieve

    @staticmethod
    def check_retrieve_status(async_process_id, include_zip, session_id, metadata_url, client_name):
        """
        This checks the status of the retrieve request. You can have the response
        include a zip file if you wish, or you can set that to false and get the
        zip in a later response

        Args:
            async_process_id (str): Required. The ID of the component that’s
                                    being deployed or retrieved.
            include_zip (bool): This tells the process whether or not to
                                include the zip file in the result or. Starting
                                with API version 34.0, pass a boolean value for
                                the include_zip argument of checkRetrieveStatus()
                                to indicate whether to retrieve the zip file.
                                The include_zip argument gives you the option to
                                retrieve the file in a separate process after
                                the retrieval operation is completed.
            session_id (str): The session ID that the login call returns.
            metadata_url (str): The Url used to send this request to
            client_name (str): A value that identifies an API client. This is
                               used for partner applications.

        Returns:
            object: Returns the status of the existing metadata retrieve request
        """
        soap_headers = Metadata.get_soap_headers(session_id, client_name, None, None)

        client_service = Metadata.get_client_service(metadata_url)
        this_retrieve_status = client_service.checkRetrieveStatus(async_process_id, include_zip,
                                                                  _soapheaders=soap_headers)

        return this_retrieve_status

    @staticmethod
    def cancel_deploy(deploy_id, session_id, metadata_url, client_name):
        """
        This method cancels the deploy

        Args:
            deploy_id (str): The Id returned from the deploy request
            session_id (str): The session ID that the login call returns.
            metadata_url (str): The Url used to send this request to
            client_name (str): A value that identifies an API client. This is
                               used for partner applications

        Returns:
            object: Returns the result of the cancel deploy request
        """
        soap_headers = Metadata.get_soap_headers(session_id, client_name, None, None)

        client_service = Metadata.get_client_service(metadata_url)
        cancel_deploy_result = client_service.cancelDeploy(deploy_id, _soapheaders=soap_headers)

        return cancel_deploy_result

    @staticmethod
    def check_deploy_status(deploy_id, include_details, session_id, metadata_url, client_name):
        """
        This method checks the status of the requested deploy

        Args:
            deploy_id             The Id returned from the deploy request
            include_details       Sets the DeployResult object to include
                                    DeployDetails information ((true) or not
                                    (false). The default is false. Available in
                                    API version 29.0 and later.
            session_id            The session ID that the login call returns.
            metadata_url          The Url used to send this request to
            client_name           A value that identifies an API client. This is
                                    used for partner applications
        """
        soap_headers = Metadata.get_soap_headers(session_id, client_name, None, None)

        client_service = Metadata.get_client_service(metadata_url)
        check_deploy_result = client_service.checkDeployStatus(deploy_id, include_details, _soapheaders=soap_headers)

        return check_deploy_result

    @staticmethod
    def create_metadata(metadata_list, session_id, metadata_url, client_name, all_or_none):
        """
        Adds one or more new metadata components to your organization synchronously.

        Args:
            metadata_list (array): Array of one or more metadata components.
                                   Limit: 10. (For CustomMetadata and
                                   CustomApplication only, the limit is 200.)
                                   You must submit arrays of only one type of
                                   component. For example, you can submit an
                                   array of 10 custom objects or 10 profiles,
                                   but not a mix of both types.
            session_id (str): The session ID that the login call returns.
            metadata_url (str): The Url used to send this request to
            client_name (str): A value that identifies an API client. This is
                               used for partner applications
            all_or_none (bool): Set to true to cause all metadata changes to
                                be rolled back if any records in the call
                                cause failures. Set to false to enable saving
                                only the records that are processed
                                successfully when other records in the call
                                cause failures.

        Returns:
            object: Returns the results of the create metadata request
        """
        soap_headers = Metadata.get_soap_headers(session_id, client_name, all_or_none, None)

        client_service = Metadata.get_client_service(metadata_url)
        create_metadata_result = client_service.createMetadata(metadata_list, _soapheaders=soap_headers)

        return create_metadata_result

    @staticmethod
    def delete_metadata(metadata_type, full_names, session_id, metadata_url, client_name, all_or_none):
        """
        Deletes one or more metadata components from your organization synchronously.

        Args:
            metadata_type (str): The metadata type of the components to delete.
            full_names (array): Array of full names of the components to delete.
                                Limit: 10. (For CustomMetadata and
                                CustomApplication only, the limit is 200.)
                                You must submit arrays of only one type of
                                component. For example, you can submit an
                                array of 10 custom objects or 10 profiles, but
                                not a mix of both types.
            session_id (str): The session ID that the login call returns.
            metadata_url (str): The Url used to send this request to
            client_name (str): A value that identifies an API client. This is
                               used for partner applications
            all_or_none (bool): Set to true to cause all metadata changes to
                                be rolled back if any records in the call
                                cause failures. Set to false to enable saving
                                only the records that are processed
                                successfully when other records in the call
                                cause failures.

        Returns:
            object: Returns the result of the delete metadata request
        """
        soap_headers = Metadata.get_soap_headers(session_id, client_name, all_or_none, None)

        client_service = Metadata.get_client_service(metadata_url)
        delete_metadata_result = client_service.deleteMetadata(metadata_type, full_names, _soapheaders=soap_headers)

        return delete_metadata_result

    @staticmethod
    def deploy(zip_file, deploy_options, session_id, metadata_url, client_name, debug_categories):
        """
        Uses file representations of components to create, update, or delete those
        components in a Salesforce org.

        Args:
            zip_file (file): Base 64-encoded binary data. Client applications
                             must encode the binary data as base64.
            deploy_options (object): Encapsulates options for determining which
                                     packages or files are deployed.
            session_id (str): The session ID that the login call returns.
            metadata_url (str): The Url used to send this request to
            client_name (str): A value that identifies an API client. This is
                               used for partner applications
            debug_categories (array): A list of log categories with their
                                      associated log levels.

        Returns:
            object: Returns the result of a Metadata deploy request
        """
        soap_headers = Metadata.get_soap_headers(session_id, client_name, None, debug_categories)

        client_service = Metadata.get_client_service(metadata_url)
        deploy_result = client_service.deploy(zip_file, deploy_options, _soapheaders=soap_headers)

        return deploy_result

    @staticmethod
    def deploy_recent_validation(validation_id, session_id, metadata_url, client_name, debug_categories):
        soap_headers = Metadata.get_soap_headers(session_id, client_name, None, debug_categories)

        client_service = Metadata.get_client_service(metadata_url)
        deploy_validation_result = client_service.deployRecentValidation(validation_id, _soapheaders=soap_headers)

        return deploy_validation_result

    @staticmethod
    def describe_metadata(as_of_version, session_id, metadata_url, client_name):
        soap_headers = Metadata.get_soap_headers(session_id, client_name, None, None)

        client_service = Metadata.get_client_service(metadata_url)
        describe_metadata_result = client_service.describeMetadata(as_of_version, _soapheaders=soap_headers)

        return describe_metadata_result

    @staticmethod
    def describe_value_type(value_type, session_id, metadata_url):
        soap_headers = Metadata.get_soap_headers(session_id, None, None, None)

        client_service = Metadata.get_client_service(metadata_url)
        describe_value_type = client_service.describeValueType(value_type, _soapheaders=soap_headers)

        return describe_value_type

    @staticmethod
    def list_metadata(list_metadata_query, as_of_version, session_id, metadata_url, client_name):
        soap_headers = Metadata.get_soap_headers(session_id, client_name, None, None)

        client_service = Metadata.get_client_service(metadata_url)
        list_metadata_result = client_service.listMetadata(list_metadata_query, as_of_version,
                                                           _soapheaders=soap_headers)

        return list_metadata_result

    @staticmethod
    def read_metadata(metadata_type, full_names, session_id, metadata_url, client_name):
        soap_headers = Metadata.get_soap_headers(session_id, client_name, None, None)

        client_service = Metadata.get_client_service(metadata_url)
        read_metadata_result = client_service.readMetadata(metadata_type, full_names, _soapheaders=soap_headers)

        return read_metadata_result

    @staticmethod
    def rename_metadata(metadata_type, old_full_name, new_full_name, session_id, metadata_url, client_name):
        soap_headers = Metadata.get_soap_headers(session_id, client_name, None, None)

        client_service = Metadata.get_client_service(metadata_url)
        rename_metadata_result = client_service.renameMetadata(metadata_type, old_full_name, new_full_name,
                                                               _soapheaders=soap_headers)

        return rename_metadata_result

    @staticmethod
    def update_metadata(metadata_list, session_id, metadata_url, client_name, all_or_none):
        soap_headers = Metadata.get_soap_headers(session_id, client_name, all_or_none, None)

        client_service = Metadata.get_client_service(metadata_url)
        update_metadata_result = client_service.updateMetadata(metadata_list, _soapheaders=soap_headers)

        return update_metadata_result

    @staticmethod
    def upsert_metadata(metadata_list, session_id, metadata_url, client_name, all_or_none):
        soap_headers = Metadata.get_soap_headers(session_id, client_name, all_or_none, None)

        client_service = Metadata.get_client_service(metadata_url)
        upsert_metadata_result = client_service.upsertMetadata(metadata_list, _soapheaders=soap_headers)

        return upsert_metadata_result
