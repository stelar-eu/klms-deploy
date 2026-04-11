from stelar.client import Client

client = Client(
    base_url="https://klms.stelar.vsamtuc.top/",
    username="admin",
    password="stelar1234-hd5jvyguk",
    tls_verify=True,
)

print("Organizations:", client.organizations[:20])
print("Datasets:", client.datasets[:10])

if client.datasets[:1]:
    d = client.datasets[:1][0]
    print("Sample dataset:", d.name)
    print("Sample resources:", d.resources)
    if d.resources:
        r = d.resources[0]
        print("Sample resource URL:", r.url)
