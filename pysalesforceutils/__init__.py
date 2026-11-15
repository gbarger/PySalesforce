#!/usr/bin/python3

"""
This package creates methods to easily call the various Salseforce APIs.
"""

import os

# These constants must be defined before the imports below, because the modules
# being imported read them from this package. Keeping them here means they can
# still be overridden, e.g. pysalesforceutils.API_VERSION = '60.0'
API_VERSION = '67.0'
METADATA_WSDL_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'WSDL', 'metadata.wsdl')
METADATA_SANDBOX_WSDL_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'WSDL', 'metadata_sandbox.wsdl')

METADATA_SERVICE_BINDING = '{http://soap.sforce.com/2006/04/metadata}MetadataBinding'
PARTNER_WSDL_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'WSDL', 'partner.wsdl')
PARTNER_SANDBOX_WSDL_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'WSDL', 'partner_sandbox.wsdl')

from . import webservice
from .util import Util
from .authentication import Authentication
from .tooling import Tooling
from .standard import Standard
from .bulk import Bulk
from .bulk2 import Bulk2
from .metadata import Metadata
from .client import Salesforce
