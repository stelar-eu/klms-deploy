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

    jsonnet_content = '''
    local tk_env = import 'spec.json';
    local urllib = import "urllib.libsonnet";
    local t = import 'transform.libsonnet';

    {
        platform:: {

        },

        workload:: {

        },

        config:: {

        },

        manifests: t.transform()
    }
    '''

    #write to main.jsonnet file
    with open(path_to_jsonnet, 'w') as jsonnet_file:
        jsonnet_file.write(jsonnet_content)

    

if __name__ == "__main__":
    main()

    
