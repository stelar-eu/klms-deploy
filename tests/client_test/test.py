from stelar.client import Client

# --- fill these in ---
BASE_URL = "https://klms.stelar.vsamtuc.top/"
USERNAME = "admin"
PASSWORD = "stelar1234-hd5jvyguk"

# Set to False only if your deployment uses a self-signed/untrusted cert
TLS_VERIFY = True


def main():
    try:
        client = Client(
            base_url=BASE_URL,
            username=USERNAME,
            password=PASSWORD,
            tls_verify=TLS_VERIFY,
        )

        # simplest real API check
        datasets = client.datasets[:1]

        print("✅ Connection successful.")
        print(f"Deployment: {BASE_URL}")
        print(f"Authenticated as: {USERNAME}")
        print(f"Dataset query succeeded. Returned {len(datasets)} item(s).")

    except Exception as e:
        print("❌ Connection test failed.")
        print(f"Deployment: {BASE_URL}")
        print(f"User: {USERNAME}")
        print(f"Error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
