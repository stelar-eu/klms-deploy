from kubernetes import client, config #need to pip install kubernetes
import base64
import sys
import json
import os
import yaml

config.load_kube_config()



def process_yaml_file(yaml_file):
    with open(yaml_file, 'r') as file:
        data = yaml.safe_load(file)
    return data


#function to create a Kubernetes secret
def create_k8s_secret(secret_name, namespace, data_dict):
    # Encode data to base64 as required by Kubernetes secrets
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

    # Output YAML for verification
    print("Generated Kubernetes Secret YAML:")
    print(yaml.dump(secret))

    return secret

# Function to apply the secret to the Kubernetes cluster
def apply_secret_to_cluster(secret):
    # Initialize Kubernetes client
    v1 = client.CoreV1Api()

    # Create the secret in the specified namespace
    try:
        v1.create_namespaced_secret(
            namespace=secret["metadata"]["namespace"],
            body=secret
        )
        print(f"Secret '{secret['metadata']['name']}' created in namespace '{secret['metadata']['namespace']}'.")
    except client.exceptions.ApiException as e:
        if e.status == 409:
            print(f"Secret '{secret['metadata']['name']}' already exists.")
        else:
            print(f"Failed to create secret: {e}")



def main():

    if len(sys.argv) != 2:
        print("Usage: python python_prog.py <file.yaml>")

    yaml_file = sys.argv[1]

    #extract values from yaml file
    yaml_data = process_yaml_file(yaml_file=yaml_file)
    print(yaml_data)

    ##################################################
    ############# spec.json ##########################
    ##################################################

    #add a tanka environment and configure spec.json using the extracted values from the input yaml
    cmd = 'tk env add environments/'+ yaml_data["env_name"] + ' --context-name ' + yaml_data["k8s_context"] + ' --namespace default'
    os.system(cmd)
    
    #open spec.json file to add additional configuration
    path_to_json = f'environments/{yaml_data["env_name"]}/spec.json'

    with open(path_to_json,'r') as json_file:
        json_data = json.load(json_file)
    
    metadata_namespace = f'environmnets/{yaml_data["env_name"]}/main.jsonnet'
    spec_resourceDefault_annotations = {"stelar.eu/author":"vsamoladas@tuc.gr"}
    spec_resourceDefault_labels = {"app.kubernetes.io/managed-by":"tanka","app.kubernetes.io/part-of":"stelar","stelar.deployment":"main"}
    
    json_data["metadata"]["namespace"] = metadata_namespace
    json_data["spec"]["resourceDefaults"]["annotations"] = spec_resourceDefault_annotations
    json_data["spec"]["resourceDefaults"]["labels"] = spec_resourceDefault_labels

    #write to spec.json file
    with open(path_to_json, 'w') as json_file:
        json.dump(json_data, json_file, indent=2)

    ##################################################
    ############# kubernetes secrets #################
    ##################################################

    secrets_list = []

    # print(yaml_data)
    for secr in yaml_data['secrets']:
        secret_dict = {
            "secret_name": secr['name'],
            "secret_data": secr['data']
            # "username": temp['username'],
            # "password": temp['password']
        }
        secrets_list.append(secret_dict)
    
    for secret in secrets_list:
        secret_yaml = create_k8s_secret(secret["secret_name"], 'default', secret["secret_data"][0])
        apply_secret_to_cluster(secret_yaml)


    # print(secret_yaml)
    ##################################################
    ############# main.jsonnet #######################
    ##################################################

    print(yaml_data["dns"][0]["subdomains"])
        


    #open main.jsonnet file for modification
    path_to_jsonnet = f'environments/{yaml_data["env_name"]}/main.jsonnet'

    jsonnet_content = config_template = f"""
    local tk_env = import 'spec.json';
    local urllib = import "urllib.libsonnet";
    local t = import 'transform.libsonnet';
    local defaults = import 'pim.libsonnet';
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
    cluster::{{
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
        
        self.cluster,
        
        + {{
        api: {{
            SMTP_SERVER: "{yaml_data["config"][0]["smtp_server"]}",
            SMTP_PORT: "{yaml_data["config"][0]["smtp_port"]}",
            SMTP_USERNAME: "{yaml_data["config"][0]["smtp_username"]}",
        }}
        }}
        + {{
        secrets:{{
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
                ONTOP_IMAGE: "vsam/stelar-okeanos:ontop",
                KEYCLOAK_IMAGE:"quay.io/keycloak/keycloak:latest",
                REDIS_IMAGE:"redis:7",
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
        import 'ckan.libsonnet',
        import 'stelarapi.libsonnet',
        import 'ontop.libsonnet',
        import 'minio.libsonnet',
        import 'keycloak.libsonnet',
        import 'stelar_ingress.libsonnet',
    ],
    /*
        Translate to manifests. This will call the
        manifest function of each component above,
        passing the PIM and Config as arguments. This
        will generate the manifests for all services
        of the cluster. PIM and config are commonly passed
        between the service manifests to achieve
        integrity and universality for all parameters.
    */
    manifests: t.transform_pim($.pim, $.configuration, $.components)
    }}
    """
    #write to main.jsonnet file
    with open(path_to_jsonnet, 'w') as jsonnet_file:
        jsonnet_file.write(jsonnet_content)

    

if __name__ == "__main__":
    main()

    
