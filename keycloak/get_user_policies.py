"""
Get the access token for a user, from the stelar realm
"""

import requests
import json

def get_secret(pass_path):
    """This function uses the UNIX 'pass' utility to retrieve the 'minio'
    client secret. 

    This must have been preconfigured by the user...

    Arguments:

    pass_path
        The full pathname of the client secret pass path
    """
    import qpass
    store = qpass.PasswordStore()
    pes = store.smart_search(pass_path)
    if len(pes) != 1:
        raise ValueError(f"The secret '{pass_path}' has matched {len(pes)} entries")
    return pes[0].password




def get_access_token(server, realm, client_id, client_secret, username, password):
    URL = f"https://{server}/realms/{realm}/protocol/openid-connect/token"
    data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'password',
        'username': username,
        'password': password
    }
    resp = requests.post(URL, data=data)

    if resp.ok:
        return resp.json()
    raise

if __name__=='__main__':
    username = input("Type username: ")

    # Look up user
    server = "authst.vsamtuc.top"
    realm = "stelarstaging2"
    client_id = 'miniost',
    client_secret = get_secret("stelar/staging/miniost-client-secret"),
    
    password = get_secret(f"stelar/staging/{username}")
    token = get_access_token(server=server, realm=realm, 
                             client_id=client_id, client_secret=client_secret, 
                             username=username, password=password)
    
    print(json.dumps(token, indent=4))
