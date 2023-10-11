"""
Functionality related to data store access and operations.
"""

import requests
import xmltodict
from urllib.parse import urljoin


class S3Store:
    """
    A proxy to an S3 API server. 

    This is mostly tested on MINIO, but effort is made to be compatible with other
    S3 services.
    """

    def __init__(self, server_url):
        self.server_url = server_url

    def assume_role_with_web_identity(self, web_token):
        """Return a parsed version of the AssumeRole result

        Args:
            web_token (str): The JWT token from an external identity provider

        Returns:
            dict: the assume-role response, including credentials
        """
        action = f"?Action=AssumeRoleWithWebIdentity\
&WebIdentityToken={web_token}\
&Version=2011-06-15\
&DurationSeconds=86400"
    
        # Omit parameters "RoleARN=role&Policy={}"
        url = urljoin(self.server_url, action)

        resp = requests.post(url)
        if resp.ok:
            return xmltodict.parse(resp.content)
        resp.raise_for_status()
