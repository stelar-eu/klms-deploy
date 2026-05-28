from kubernetes import client, config
import base64
import sys
import json
import os
import yaml
import textwrap
import random
import string



def verify_cluster_issuer(issuer_name):
    """Checks if the ClusterIssuer from YAML exists and is Ready."""
    if not issuer_name:
        return False

    print(f"🔍 Verifying ClusterIssuer: {issuer_name}...")
    custom_api = client.CustomObjectsApi()
    
    try:
        issuer = custom_api.get_cluster_custom_object(
            group="cert-manager.io",
            version="v1",
            plural="clusterissuers",
            name=issuer_name
        )
        
        status_conditions = issuer.get('status', {}).get('conditions', [])
        is_ready = any(c.get('type') == 'Ready' and c.get('status') == 'True' for c in status_conditions)
        
        if is_ready:
            print(f"✅ ClusterIssuer '{issuer_name}' is Ready.")
            return True
    except Exception:
        print(f"⚠️ ClusterIssuer '{issuer_name}' not found. Falling back to manual mode.")
    
    return False


def process_yaml_file(yaml_file):
    with open(yaml_file, "r") as file:
        data = yaml.safe_load(file)
    return data


# Method to create a Kubernetes secret
def create_k8s_secret(secret_name, namespace, data_dict):
    # Encode data to base64 as required by Kubernetes secrets
    print(f"🔐 Generating secret '{secret_name}'...")
    encoded_data = {
        k: base64.b64encode(v.encode("utf-8")).decode("utf-8")
        for k, v in data_dict.items()
    }

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
            namespace=secret["metadata"]["namespace"], body=secret
        )
        print(f"✅ Secret '{secret['metadata']['name']}' applied successfully.\n")
    except client.exceptions.ApiException as e:
        if e.status == 409:
            print(f"⚠️ Secret '{secret['metadata']['name']}' already exists.\n")
        else:
            print(f"❌ Failed to apply secret: {e}\n")


def generate_jwt_key(length=43):
    characters = string.ascii_letters + string.digits
    return f"string:{''.join(random.choices(characters, k=length))}"


def generate_random_string(length=40, chunk_size=8, separator='-'):
    characters = string.ascii_letters + string.digits
    raw_string = ''.join(random.choices(characters, k=length))
    chunks = [raw_string[i:i+chunk_size] for i in range(0, length, chunk_size)]
    return separator.join(chunks)


def generate_ckan_secrets(namespace):
    secret_data = {}
    # Create session secret
    secret_data["session-key"] = generate_random_string(40, 8, "-")
    # Create JWT encode key
    secret_data["jwt-key"] = generate_jwt_key()

    apply_secret_to_cluster(create_k8s_secret("ckan-auth-secret",
                                              namespace,
                                              secret_data))


def create_tls_secret(namespace, cert_path, key_path):
    print(f"🔐 Attempting to create TLS secret '{namespace}-tls'...")

    if not os.path.exists(cert_path):
        print(
            f"⚠️ Certificate file '{cert_path}' not found. Skipping TLS secret creation.\n"
        )
        return None
    if not os.path.exists(key_path):
        print(f"⚠️ Key file '{key_path}' not found. Skipping TLS secret creation.\n")
        return None

    with open(cert_path, "r") as cert_file:
        cert_data = cert_file.read()
    with open(key_path, "r") as key_file:
        key_data = key_file.read()

    encoded_cert = base64.b64encode(cert_data.encode("utf-8")).decode("utf-8")
    encoded_key = base64.b64encode(key_data.encode("utf-8")).decode("utf-8")

    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": f"{namespace}-tls",
            "namespace": namespace,
        },
        "type": "kubernetes.io/tls",
        "data": {"tls.crt": encoded_cert, "tls.key": encoded_key},
    }

    apply_secret_to_cluster(secret)
    return secret


def generate_sample_yaml(file_path="example_config.yaml"):
    """
    Generates a YAML configuration file with sample values and comprehensive comments.
    """
    yaml_content = """
# This is a sample configuration file for STELAR deployment. It is provided 
# as input to the bootstrap script for generating Kubernetes secrets and
# configuring the Tanka environment.
# Environment name (e.g., "staging", "production", "minikube.dev")
env_name: "minikube.dev"

# Define either "amazon" for AWS or "minikube" for local Kubernetes
platform: "minikube"

# The Kubernetes context to use
k8s_context: "minikube"

# The Kubernetes namespace for deployment
namespace: "stelar-dev"

# The contact person for this configuration
author: "dpetrou@tuc.gr"

dns:
  - name: "minikube"  # DNS configuration name, could be "stelar.gr" or "stelar-klms.eu" for public configs
    scheme: "http"  # Scheme to use (e.g., "http" or "https")
    subdomains:
      keycloak: "kc"  # Keycloak subdomain
      minio: "minio"  # MinIO subdomain
      primary: "klms"  # Main application subdomain
      registry: "img"  # Image Registry subdomain

config:
  - smtp_server: "stelar.gr"  # SMTP server address
    smtp_port: "465"  # SMTP port (e.g., 465 for SSL, 587 for TLS)
    smtp_username: "##YOUR_SMTP_USERNAME_HERE##"  # SMTP username for authentication
    s3_console_url: "http://klms.minikube/s3/login"  # URL for the S3 console
    groq_api_url: "https://api.groq.com/"  # Groq API URL for LLM search (if enabled)
    groq_api_model: "meta-llama/llama-4-scout-17b-16e-instruct"  # Groq API model to use for LLM search (if enabled)
  
options:
  - enable_llm_search: false

secrets:
  - name: "postgresdb-secret" # Password for PostgreSQL default database 
    data:
      - password: "##YOUR_PASSWORD_HERE##"
  - name: "ckandb-secret"  # Password for PostgreSQL CKAN database 
    data:
      - password: "##YOUR_PASSWORD_HERE##"
  - name: "keycloakdb-secret" # Password for PostgreSQL Keycloak database 
    data:
      - password: "##YOUR_PASSWORD_HERE##"
  - name: "datastoredb-secret" # Password for PostgreSQL Datastore database 
    data:
      - password: "##YOUR_PASSWORD_HERE##"
  - name: "keycloakroot-secret" # Password for STELAR Administrator user 
    data:
      - password: "##YOUR_PASSWORD_HERE##"
  - name: "smtpapi-secret" # Password for SMTP server (mailing server)
    data:
      - password: "##YOUR_PASSWORD_HERE##"
  - name: "ckanadmin-secret" # Password for CKAN Administrator user
    data:
      - password: "##YOUR_PASSWORD_HERE##"
  - name: "minioroot-secret" # Password for MinIO root user
    data:
      - password: "##YOUR_PASSWORD_HERE##"
  - name: "session-secret-key" # Secret key for session management
    data:
      - key: "##YOUR_SECRET_KEY_HERE##"
  - name: "quaydb-secret" # Password for PostgreSQL Quay database
    data:
      - password: "##YOUR_PASSWORD_HERE##"

  # Uncomment the following lines to add a Groq API key secret if the LLM search is enabled
  # - name: "groq-api-key"
  #   data:
  #     - key: "##YOUR_API_KEY_HERE##"  
    """
    with open(file_path, "w") as file:
        file.write(yaml_content)
        
    print("📝 YAML sample configuration file 'example_config.yaml' has been generated successfully.")


#returns [dynamic_storage_class, provisioning_storage_class]
def get_storage_classes(platform):
    if platform == "minikube":
        return "longhorn", "csi-hostpath-sc"
    elif platform == "okeanos":
        return "longhorn", "longhorn"
    else:  # Default to Amazon's storage class
        return "ebs-sc", "ebs-sc"
    
#returns the value for the insecure MinIO client flag based on platform and any overrides
def get_insecure_minio_flag(platform,override="true"):
    if platform == "minikube" or override == "true":
        return "true"
    else:
        return "false"


def generate_jsonnet_content(yaml_data, secrets_list, insecure_minio_override, cluster_issuer):
    print("📝 Generating JSONNet main file content...")

    # 1. Determine storage classes based on platform
    dynamic_storage_class, provisioning_storage_class = get_storage_classes(yaml_data["platform"])

    # 2. Determine insecure MinIO client flag
    insecure_minio = get_insecure_minio_flag(yaml_data["platform"], insecure_minio_override)

    # 3. Format issuer for Jsonnet
    issuer_val = f"'{cluster_issuer}'" if cluster_issuer != "null" else "null"

    jsonnet_content = textwrap.dedent(
        f"""
    local tk_env = import 'spec.json';
    local urllib = import "unused/urllib.libsonnet";
    local t = import 'util/transform.libsonnet';
    local defaults = import 'util/pim.libsonnet';
    local secrets = import 'secrets.libsonnet';
    local systeminit = import 'deployment/systeminit.libsonnet';

    {{
      _tk_env:: tk_env.spec,
      _config+:: {{
        namespace: tk_env.spec.namespace,
        dynamicStorageClass: '{dynamic_storage_class}',
      }},
      provisioning:: {{
        namespace: $._config.namespace,
        dynamic_volume_storage_class: '{provisioning_storage_class}',
      }},
      access:: {{
        endpoint: {{
          scheme: '{yaml_data["dns"][0]["scheme"]}',
          host: '{yaml_data["dns"][0]["name"]}',
          port: null,
        }},
      }},
      cluster:: {{
        endpoint: {{
          SCHEME: "{yaml_data["dns"][0]["scheme"]}",
          ROOT_DOMAIN: "{yaml_data["dns"][0]["name"]}",
          CLUSTER_ISSUER: {issuer_val},  // <--- ADDED FOR CERT-MANAGER
          PRIMARY_SUBDOMAIN: "{yaml_data["dns"][0]["subdomains"][2]["primary"]}",
          KEYCLOAK_SUBDOMAIN: "{yaml_data["dns"][0]["subdomains"][0]["keycloak"]}",
          MINIO_API_SUBDOMAIN: "{yaml_data["dns"][0]["subdomains"][1]["minio"]}",
          REGISTRY_SUBDOMAIN: "{yaml_data["dns"][0]["subdomains"][3]["registry"]}",
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
            INSECURE_MC_CLIENT: '{insecure_minio}',
          }}
        }}
        + {{
          llm_search: {{
            ENABLE_LLM_SEARCH: {"'true'" if yaml_data["options"][0]["enable_llm_search"] else "'false'"},
            GROQ_API_URL: "{yaml_data["config"][0]["groq_api_url"] if yaml_data["options"][0]["enable_llm_search"] else "null"}",
            GROQ_MODEL: "{yaml_data["config"][0]["groq_model"] if yaml_data["options"][0]["enable_llm_search"] else "null"}",
          }}
        }}
        + {{
          secrets: {{
            db: {{
              postgres_db_password_secret: "{secrets_list[0]["secret_name"]}",
              ckan_db_password_secret: "{secrets_list[1]["secret_name"]}",
              keycloak_db_passowrd_secret: "{secrets_list[2]["secret_name"]}",
              datastore_db_password_secret: "{secrets_list[3]["secret_name"]}",
              quay_db_password_secret: "{secrets_list[9]["secret_name"]}",
            }},
            keycloak: {{
              root_password_secret: "{secrets_list[4]["secret_name"]}",
            }},
            api: {{
              smtp_password_secret: "{secrets_list[5]["secret_name"]}",
              session_secret_key: "{secrets_list[8]["secret_name"]}",
            }},
            ckan: {{
              ckan_admin_password_secret: "{secrets_list[6]["secret_name"]}",
              ckan_auth_secret: "ckan-auth-secret",
            }},
            minio: {{
              minio_root_password_secret: "{secrets_list[7]["secret_name"]}",
            }},
            llm_search: {{
              groq_api_key_secret: "{secrets_list[10]["secret_name"] if yaml_data["options"][0]["enable_llm_search"] else "null"}",
            }}
          }}
        }},
      pim::
        self.provisioning
        + {{
            images: {{
              API_IMAGE: 'petroud/stelar-api:prod',
              CKAN_IMAGE: 'petroud/stelar-tuc:ckan',
              POSTGIS_IMAGE:"petroud/stelar-tuc:postgres",
              MINIO_IMAGE:"quay.io/minio/minio:RELEASE.2025-04-22T22-12-26Z-cpuv1",
              ONTOP_IMAGE: "petroud/stelar-tuc:ontop",
              KEYCLOAK_IMAGE:"petroud/stelar-tuc:keycloak",
              REDIS_IMAGE:"redis:7",
              KC_INIT:"petroud/stelar-tuc:kcinit",
              REGISTRY_IMAGE: "petroud/stelar-tuc:registry",
              REGISTRY_INIT: "petroud/stelar-tuc:registry-init",
              VISUALIZER_IMAGE: "petroud/profvisualizer:latest",
              SDE_MANAGER_IMAGE: "petroud/sde-manager:latest",
              PREVIEWER_IMAGE: "petroud/stelar-previewer:latest",
              LLM_SEARCH_IMAGE: "petroud/semantic-dataset-search:latest",
             }},
        }}
        + defaults,

      components:: [
        import 'deployment/db.libsonnet',
        import 'deployment/redis.libsonnet',
        import 'deployment/ontop.libsonnet',
        import 'deployment/minio.libsonnet',
        import 'deployment/keycloak.libsonnet',
        import 'deployment/stelarapi.libsonnet',
        import 'deployment/stelar_ingress.libsonnet',
        import 'deployment/ckan.libsonnet',
        systeminit('full'),
        import 'deployment/registry.libsonnet',
        import 'deployment/visualizer.libsonnet',
        import 'deployment/previewer.libsonnet',
        import 'deployment/network.libsonnet',
        {'import "deployment/llmsearch.libsonnet",' if yaml_data["options"][0]["enable_llm_search"] else ''}
      ],
      manifests: t.transform_pim($.pim, $.configuration, $.components)
    }}
    """
    )
    return jsonnet_content


def write_jsonnet_file(path_to_jsonnet, yaml_data, secrets_list, insecure_minio_override, cluster_issuer):
    print(f"🖊️ Writing JSONNet file to {path_to_jsonnet}...")
    jsonnet_content = generate_jsonnet_content(yaml_data, secrets_list, insecure_minio_override, cluster_issuer)
    with open(path_to_jsonnet, "w") as jsonnet_file:
        jsonnet_file.write(jsonnet_content)
    print(f"✅ JSONNet file written successfully at {path_to_jsonnet}.")


def parse_args():
    if "-f" not in sys.argv and "-sample" not in sys.argv:
        print(
            "❌ Usage: python bootstrap.py -f <file.yaml> [-cert <cert_path> -key <key_path>] or python bootstrap.py -sample to generate a sample YAML file."
        )
        sys.exit(1)

    if "-sample" in sys.argv:
        generate_sample_yaml()
        sys.exit(0)

    yaml_file = sys.argv[sys.argv.index("-f") + 1]
    cert_path = sys.argv[sys.argv.index("-cert") + 1] if "-cert" in sys.argv else None
    key_path = sys.argv[sys.argv.index("-key") + 1] if "-key" in sys.argv else None

    if (cert_path and not key_path) or (key_path and not cert_path):
        print(
            "❌ Both -cert and -key arguments must be provided to create a TLS secret."
        )
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

    if not yaml_data["namespace"]:
        raise ValueError(
            "❌ Namespace field cannot be left blank. Enter a valid Kubernetes namespace name."
        )


    k8s_context = yaml_data.get('k8s_context', None)
    if not k8s_context:
        raise ValueError(
            "❌ k8s_context field cannot be omitted. Set to a valid kubectl context."
        )
    config.load_kube_config(context=k8s_context)

    
    scheme = yaml_data["dns"][0]["scheme"]

    # 1. Check if ClusterIssuer is defined in YAML and if it actually exists/is ready
    target_issuer = yaml_data.get('cluster_issuer')
    use_cert_manager = verify_cluster_issuer(target_issuer)

    if use_cert_manager and scheme == "https":
        # If Cert-Manager is ready, we don't need local files and we can trust SSL
        insecure_minio = "false"
        cluster_issuer = target_issuer
        print(f"✨ SSL Mode: Automated via Cert-Manager ({target_issuer})")
    else:
        # Fallback: Use local files if provided, otherwise default to insecure
        cluster_issuer = "null"
        if cert_path and key_path:
            print("🔐 SSL Mode: Manual (using provided .pem files)")
            insecure_minio = "false" # Trusting you provided valid files
        else:
            print("⚠️ SSL Mode: Insecure/Self-signed (Fallback)")
            insecure_minio = "true"


    print("🌐 Setting up Tanka environment...")
    cmd = f'tk env add environments/{yaml_data["env_name"]} --context-name {yaml_data["k8s_context"]} --namespace {yaml_data["namespace"]}'
    os.system(cmd)
    print(f"✅ Tanka environment '{yaml_data['env_name']}' configured.")

    path_to_json = f'environments/{yaml_data["env_name"]}/spec.json'
    print("⚙️ Updating spec.json...")
    with open(path_to_json, "r") as json_file:
        json_data = json.load(json_file)

    json_data["metadata"][
        "namespace"
    ] = f'environmnets/{yaml_data["env_name"]}/main.jsonnet'
    json_data["spec"]["injectLabels"] = True
    json_data["spec"]["resourceDefaults"]["annotations"] = {
        "stelar.eu/author": yaml_data["author"]
    }
    json_data["spec"]["resourceDefaults"]["labels"] = {
        "app.kubernetes.io/managed-by": "tanka",
        "app.kubernetes.io/part-of": "stelar",
        "stelar.deployment": "main",
    }

    with open(path_to_json, "w") as json_file:
        json.dump(json_data, json_file, indent=2)
    print("✅ spec.json updated successfully.\n")

    secrets_list = []
    for secr in yaml_data["secrets"]:
        secrets_list.append({"secret_name": secr["name"], "secret_data": secr["data"]})

    for secret in secrets_list:
        secret_yaml = create_k8s_secret(
            secret["secret_name"], yaml_data["namespace"], secret["secret_data"][0]
        )
        apply_secret_to_cluster(secret_yaml)

    # Generate CKAN auth secrets
    generate_ckan_secrets(yaml_data["namespace"])

    # If a certificate and key file were provided then generate the TLS secret certificate
    if cert_path and key_path:
        create_tls_secret(yaml_data["namespace"], cert_path, key_path)

    path_to_jsonnet = f'environments/{yaml_data["env_name"]}/main.jsonnet'
    write_jsonnet_file(path_to_jsonnet, yaml_data, secrets_list, insecure_minio, cluster_issuer)


if __name__ == "__main__":
    main()
