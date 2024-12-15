from kubernetes import client, config
import base64
import sys
import json
import os
import yaml
import textwrap

config.load_kube_config()

def process_yaml_file(yaml_file):
    with open(yaml_file, 'r') as file:
        data = yaml.safe_load(file)
    return data


# Method to create a Kubernetes secret
def create_k8s_secret(secret_name, namespace, data_dict):
    # Encode data to base64 as required by Kubernetes secrets
    print(f"🔐 Generating secret '{secret_name}'...")
    encoded_data = {k: base64.b64encode(v.encode("utf-8")).decode("utf-8") for k, v in data_dict.items()}

    # Define the secret structure
    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": secret_name,
            "namespace": namespace,
        },
        "type": "Opaque",
        "data": encoded_data,
    }   
    print(f"✅ Secret '{secret_name}' generated.")
    return secret

# Method to apply the secret to the Kubernetes cluster
def apply_secret_to_cluster(secret):
    print(f"🚀 Applying secret '{secret['metadata']['name']}' to the K8s cluster...")
    v1 = client.CoreV1Api()
    try:
        v1.create_namespaced_secret(
            namespace=secret["metadata"]["namespace"],
            body=secret
        )
        print(f"✅ Secret '{secret['metadata']['name']}' applied successfully.\n")
    except client.exceptions.ApiException as e:
        if e.status == 409:
            print(f"⚠️ Secret '{secret['metadata']['name']}' already exists.\n")
        else:
            print(f"❌ Failed to apply secret: {e}\n")


def create_tls_secret(namespace, cert_path, key_path):
    print(f"🔐 Attempting to create TLS secret '{namespace}-tls'...")
    
    if not os.path.exists(cert_path):
        print(f"⚠️ Certificate file '{cert_path}' not found. Skipping TLS secret creation.\n")
        return None
    if not os.path.exists(key_path):
        print(f"⚠️ Key file '{key_path}' not found. Skipping TLS secret creation.\n")
        return None

    with open(cert_path, 'r') as cert_file:
        cert_data = cert_file.read()
    with open(key_path, 'r') as key_file:
        key_data = key_file.read()
    
    encoded_cert = base64.b64encode(cert_data.encode('utf-8')).decode('utf-8')
    encoded_key = base64.b64encode(key_data.encode('utf-8')).decode('utf-8')

    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": f"{namespace}-tls",
            "namespace": namespace,
        },
        "type": "kubernetes.io/tls",
        "data": {
            "tls.crt": encoded_cert,
            "tls.key": encoded_key
        },
    }

    apply_secret_to_cluster(secret)
    return secret

def generate_jsonnet_content(yaml_data, secrets_list):
    print("📝 Generating JSONNet main file content...")
    
    jsonnet_content = textwrap.dedent(f"""
    local tk_env = import 'spec.json';
    local urllib = import "urllib.libsonnet";
    local t = import 'transform.libsonnet';
    local defaults = import 'pim.libsonnet';
    local secrets = import 'secrets.libsonnet';

    {{
      _tk_env:: tk_env.spec,
      _config+:: {{
        namespace: tk_env.spec.namespace,
        dynamicStorageClass: 'ebs-sc',
      }},
      provisioning:: {{
        namespace: $._config.namespace,
        dynamic_volume_storage_class: 'ebs-sc',
      }},
      access:: {{
        // Root Domain Name to the host of the STELAR deployment
        endpoint: {{
          scheme: '{yaml_data["dns"][0]["scheme"]}',
          host: '{yaml_data["dns"][0]["name"]}',
          port: null,
        }},
      }},
      cluster:: {{
        endpoint: {{
          /*
          In order for the cluster to be able to operate,
          (3) subdomains (belonging to ROOT_DOMAIN) are needed:
          - PRIMARY:  It is the subdomain at which
                      the main reverse proxy listens.
                      Services as the Data API, Console,
                      MinIO Console, OnTop, DC are covered
                      by this.
          - KEYCLOAK: Keycloak SSO server needs a dedicated
                      domain in order to serve SSO to services.
                      We choose here to use subdomain which
                      will work just fine.
          - MINIO_API: In order to avoid conflicts with MinIO
                      paths (confusing a MinIO path for a
                      reverse proxy path) we choose to use
                      separate subdomain for the MinIO API only
                      (Note: MinIO CONSOLE is served by the
                      PRIMARY subdomain. )
          */
          SCHEME: "{yaml_data["dns"][0]["scheme"]}",
          ROOT_DOMAIN: "{yaml_data["dns"][0]["name"]}",
          PRIMARY_SUBDOMAIN: "{yaml_data["dns"][0]["subdomains"][2]["primary"]}",
          KEYCLOAK_SUBDOMAIN: "{yaml_data["dns"][0]["subdomains"][0]["keycloak"]}",
          MINIO_API_SUBDOMAIN: "{yaml_data["dns"][0]["subdomains"][1]["minio"]}",
        }}
      }},
      configuration::
        self.cluster
        + {{
          api: {{
            SMTP_SERVER: "{yaml_data["config"][0]["smtp_server"]}",
            SMTP_PORT: "{yaml_data["config"][0]["smtp_port"]}",
            SMTP_USERNAME: "{yaml_data["config"][0]["smtp_username"]}",
            S3_CONSOLE_URL: "{yaml_data["config"][0]["s3_console_url"]}",
          }}
        }}
        + {{
          minio:{{
            API_DOMAIN: '{yaml_data["dns"][0]["scheme"]}://{yaml_data["dns"][0]["subdomains"][1]["minio"]}.{yaml_data["dns"][0]["name"]}',
            CONSOLE_DOMAIN: "{yaml_data["dns"][0]["scheme"]}://{yaml_data["dns"][0]["subdomains"][2]["primary"]}.{yaml_data["dns"][0]["name"]}/s3",
          }}
        }}
        + {{
          secrets: {{
            db: {{
              postgres_db_password_secret: "{secrets_list[0]["secret_name"]}",
              ckan_db_password_secret: "{secrets_list[1]["secret_name"]}",
              keycloak_db_passowrd_secret: "{secrets_list[2]["secret_name"]}",
              datastore_db_password_secret: "{secrets_list[3]["secret_name"]}",
            }},
            keycloak: {{
              root_password_secret: "{secrets_list[4]["secret_name"]}",
            }},
            api: {{
              smtp_password_secret: "{secrets_list[5]["secret_name"]}",
            }},
            ckan: {{
              ckan_admin_password_secret: "{secrets_list[6]["secret_name"]}",
            }},
            minio: {{
              minio_root_password_secret: "{secrets_list[7]["secret_name"]}",
            }}
          }}
        }},
      ##########################################
      ## The Platform Independent Model ########
      ##########################################
      pim::
        self.provisioning
        + {{
            images: {{
              API_IMAGE: 'petroud/stelar-tuc:data-api-prod',
              CKAN_IMAGE: 'petroud/stelar-tuc:ckan',
              POSTGIS_IMAGE:"petroud/stelar-tuc:postgres",
              MINIO_IMAGE:"quay.io/minio/minio:latest",
              ONTOP_IMAGE: "petroud/stelar-tuc:ontop",
              KEYCLOAK_IMAGE:"quay.io/keycloak/keycloak:25.0",
              REDIS_IMAGE:"redis:7",
              KC_INIT:"petroud/stelar-tuc:kcinit"
            }},
        }}
        + defaults,

      /*
      Here the library for each component is
      defined in order to use them for manifest
      generation later on. The services included
      here will be actively deployed in the K8s
      cluster.
      */
      components:: [
        import 'db.libsonnet',
        import 'redis.libsonnet',
        import 'ontop.libsonnet',
        import 'minio.libsonnet',
        import 'keycloak.libsonnet',
        import 'stelarapi.libsonnet',
        import 'stelar_ingress.libsonnet',
        import 'ckan.libsonnet',
        import 'systeminit.libsonnet'
      ],
      /*
      Translate to manifests. This will call the
      manifest function of each component above,
      passing the PIM and Config as arguments. This
      will generate the manifests for all services
      of the cluster.
      */
      manifests: t.transform_pim($.pim, $.configuration, $.components)
    }}
    """)
    return jsonnet_content


def write_jsonnet_file(path_to_jsonnet, yaml_data, secrets_list):
    print(f"🖊️ Writing JSONNet file to {path_to_jsonnet}...")
    jsonnet_content = generate_jsonnet_content(yaml_data, secrets_list)
    with open(path_to_jsonnet, 'w') as jsonnet_file:
        jsonnet_file.write(jsonnet_content)
    print(f"✅ JSONNet file written successfully at {path_to_jsonnet}.")



def parse_args():
    if "-f" not in sys.argv:
        print("❌ Usage: python python_prog.py -f <file.yaml> [-cert <cert_path> -key <key_path>]")
        sys.exit(1)

    yaml_file = sys.argv[sys.argv.index("-f") + 1]
    cert_path = sys.argv[sys.argv.index("-cert") + 1] if "-cert" in sys.argv else None
    key_path = sys.argv[sys.argv.index("-key") + 1] if "-key" in sys.argv else None
    
    if (cert_path and not key_path) or (key_path and not cert_path):
        print("❌ Both -cert and -key arguments must be provided to create a TLS secret.")
        sys.exit(1)

    return yaml_file, cert_path, key_path


def main():
    
    yaml_file, cert_path, key_path = parse_args()
    yaml_data = process_yaml_file(yaml_file)

    cert_path = None
    key_path = None

    if "-cert" in sys.argv and "-key" in sys.argv:
        cert_path = sys.argv[sys.argv.index("-cert") + 1]
        key_path = sys.argv[sys.argv.index("-key") + 1]

    if not yaml_data['namespace']:
        raise ValueError('❌ Namespace field cannot be left blank. Enter a valid Kubernetes namespace name.')

    print("🌐 Setting up Tanka environment...")
    cmd = f'tk env add environments/{yaml_data["env_name"]} --context-name {yaml_data["k8s_context"]} --namespace {yaml_data["namespace"]}'
    os.system(cmd)
    print(f"✅ Tanka environment '{yaml_data['env_name']}' configured.")

    path_to_json = f'environments/{yaml_data["env_name"]}/spec.json'
    print("⚙️ Updating spec.json...")
    with open(path_to_json, 'r') as json_file:
        json_data = json.load(json_file)

    json_data["metadata"]["namespace"] = f'environmnets/{yaml_data["env_name"]}/main.jsonnet'
    json_data["spec"]["injectLabels"] = True
    json_data["spec"]["resourceDefaults"]["annotations"] = {"stelar.eu/author": yaml_data["author"]}
    json_data["spec"]["resourceDefaults"]["labels"] = {
        "app.kubernetes.io/managed-by": "tanka",
        "app.kubernetes.io/part-of": "stelar",
        "stelar.deployment": "main"
    }

    with open(path_to_json, 'w') as json_file:
        json.dump(json_data, json_file, indent=2)
    print("✅ spec.json updated successfully.\n")

    secrets_list = []
    for secr in yaml_data['secrets']:
        secrets_list.append({
            "secret_name": secr['name'],
            "secret_data": secr['data']
        })

    for secret in secrets_list:
        secret_yaml = create_k8s_secret(secret["secret_name"], yaml_data['namespace'], secret["secret_data"][0])
        apply_secret_to_cluster(secret_yaml)
      
    # If a certificate and key file were provided then generate the TLS secret certificate
    if cert_path and key_path:
        create_tls_secret(yaml_data['namespace'], cert_path, key_path)

    path_to_jsonnet = f'environments/{yaml_data["env_name"]}/main.jsonnet'
    write_jsonnet_file(path_to_jsonnet, yaml_data, secrets_list)

if __name__ == "__main__":
    main()
    
