"""Code related to SSO authentication and authorization
"""

from __future__ import annotations

import requests
import json
from urllib.parse import urljoin


class Realm:
    """
    Proxy object for accessing a realm
    """

    def __init__(self, server_url, realm_name):
        self.server_url = server_url
        self.realm_name = realm_name

    @property
    def well_known_url(self):
        return urljoin(self.server_url, f"realms/{self.realm_name}/.well-known/openid-configuration")

    def well_known(self):
        """Return the 'Well-known Urls' object for OpenID

        Returns:
            dict: the well-known configuration object
        """
        url = self.well_known_url
        resp = requests.get(url)
        if resp.ok:
            return resp.json()
        resp.raise_for_status()

    def client(self, client_id, client_secret):
        """Return a client proxy for this realm

        Args:
            client_id (str): the client id
            client_secret (str): the client secret

        Returns:
            Client: Aclient proxy object
        """
        return Client(self, client_id, client_secret)
    
    def token(self, client: Client, username: str, password: str):
        """Return access token after authenticating current user with password

        Args:
            client (Client): the OpenID client to use
            username (str): the username
            password (str): the password

        Returns:
            dict: the access token object
        """
        endpoint = f"realms/{self.realm_name}/protocol/openid-connect/token"
        URL = urljoin(self.server_url, endpoint)
        data = {
            'client_id': client.client_id,
            'client_secret': client.client_secret,
            'grant_type': 'password',
            'username': username,
            'password': password
        }
        resp = requests.post(URL, data=data)

        if resp.ok:
            return resp.json()
        resp.raise_for_status()



class Client:
    """Proxy to a client at some realm
    """
    def __init__(self, realm, client_id, client_secret):
        self.realm = realm
        self.client_id = client_id
        self.client_secret = client_secret

    def token(self, username, password):
        return self.realm.token(self, username, password)


