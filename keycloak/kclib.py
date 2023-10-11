"""
Get the access token for a user, from the stelar realm
"""

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


def minio_assume_role(minio_server, kc_client, username, password):
    atok = kc_client.token(username, password)
    token = atok['access_token']

    action = f"?Action=AssumeRoleWithWebIdentity\
&WebIdentityToken={token}\
&Version=2011-06-15\
&DurationSeconds=86400"
    
    # Omit parameters "RoleARN=role&Policy={}"
    url = urljoin(minio_server, action)

    resp = requests.post(url)
    if resp.ok:
        return resp
    resp.raise_for_status()


def get_miniost():
    import stelar.auth as sa
    server = "https://authst.vsamtuc.top/"
    realm_name = "stelarstaging2"
    client_id = 'miniost',
    client_secret = get_secret("stelar/staging/miniost-client-secret"),

    return sa.Realm(server, realm_name).client(client_id, client_secret)


def print_access_token():
    username = input("Type username: ")

    # Look up user
    cli = get_miniost()

    password = get_secret(f"stelar/staging/{username}")
    token = cli.token(username=username, password=password)
    
    print(json.dumps(token, indent=4))

