from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='pysalesforceutils',
    version='1.1.0',
    author='Glen Barger',
    author_email='gbarger@gmail.com',
    description='Python module to wrap the Salesforce APIs',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/gbarger/PySalesforce',
    packages=find_packages(),
    package_data={
        'pysalesforceutils': ['WSDL/*.wsdl'],
    },
    install_requires=[
        'requests',
        'urllib3',
    ],
    extras_require={
        'soap': ['zeep'],
    },
)