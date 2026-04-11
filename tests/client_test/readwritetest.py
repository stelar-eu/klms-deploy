from stelar.client import Client
import pandas as pd
import uuid
import time
from pathlib import Path

BASE_URL = "https://klms.stelar.vsamtuc.top"
USERNAME = "admin"
PASSWORD = "stelar1234-hd5jvyguk"
TLS_VERIFY = True

ORG_NAME = "test"
from stelar.client import Client
import pandas as pd
import uuid
import time

BASE_URL = "https://klms.stelar.vsamtuc.top"
USERNAME = "admin"
PASSWORD = "stelar1234-hd5jvyguk"
TLS_VERIFY = True
ORG_NAME = "test"

# Change this if your deployment uses a different bucket
S3_BUCKET = "klms-bucket"


def log(msg):
    print(f"\n=== {msg} ===")


def main():
    client = Client(
        base_url=BASE_URL,
        username=USERNAME,
        password=PASSWORD,
        tls_verify=TLS_VERIFY,
    )

    org = client.organizations[ORG_NAME]
    client.datasets.default_organization = org

    suffix = f"{int(time.time())}-{uuid.uuid4().hex[:6]}"
    dataset_name = f"client-smoke-{suffix}"
    dataset_title = f"Client Smoke Test {suffix}"

    input_s3 = f"s3://{S3_BUCKET}/{dataset_name}/input.csv"
    output_s3 = f"s3://{S3_BUCKET}/{dataset_name}/summary.csv"

    log("Create dataset")
    dataset = client.datasets.create(
        name=dataset_name,
        title=dataset_title,
        description="Temporary dataset created by automated STELAR client testing."
    )
    print("Created dataset:", dataset.name)
    print("Title:", dataset.title)

    df = pd.DataFrame({
        "group": ["A", "A", "B", "B", "B"],
        "value": [10, 20, 5, 7, 9],
    })

    log("Input dataframe")
    print(df)

    log("Upload dataframe as resource")
    resource = dataset.add_dataframe(df, input_s3)
    print("Resource:", resource)
    print("Resource URL:", getattr(resource, "url", None))

    log("Read dataframe back")
    df2 = resource.read_dataframe()
    print(df2)

    log("Dummy analysis")
    summary = df2.groupby("group", as_index=False).agg(
        mean_value=("value", "mean"),
        min_value=("value", "min"),
        max_value=("value", "max"),
    )
    print(summary)

    log("Upload analysis result")
    result_resource = dataset.add_dataframe(summary, output_s3)
    print("Result resource:", result_resource)
    print("Result URL:", getattr(result_resource, "url", None))

    log("Final dataset resources")
    print(dataset.resources)

    print("\nSUCCESS: upload + read + analysis flow completed.")


if __name__ == "__main__":
    main()

