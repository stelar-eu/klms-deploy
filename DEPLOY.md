# STELAR KLMS deployment


The STELAR KLMS is a Kubernetes-based system, and as such, it requires
flexible deployment logic on kubernetes clusters. 
Because of the complex nature of STELAR KLMS deployments,
we have decided to employ a **configuration-as-code** approach, by using the
(Jsonnet language)[https://jsonnet.org/] to code configuration logic.

JSonnet is a very clever extension of JSON which allows large and complex 
JSON objects to be composed in a proncipled manner. In many ways, this is reminiscent of the classis 
OMG Model-Driven Development approach, but significantly simplified.
While JSonnet is Turing complete, it is a very simple language whose principles can be 
learned by a programmer in under one hour.

## Deployment configuration

A deployment of STELAR considers several issues:

 - Accessing the system after deploymment, including
   hostname, security concerns (certificates, passwords),
   coordination with storage etc.

 - Provisioning issues, relating the the provisioning of 
   STELAR components (kubernetes version, storage arrangement,
   scheduling on nodes, resource use etc)

 - Component configurations desired (versions, storage 
   allocations to modules, optional functions, replication 
   for services, HA requirements, etc. ).


To get from the above description to a set of kubernetes manifests for deployment, we empoy a model transofrmation 
approach.


## Instructions for STELAR deployment

The deployment of STELAR requires some tools and is performed by the following steps

 1. Install Graphana Tanka and Jsonnet Bundler
 1. Update Jsonnet packages and Helm charts
 1. Have access to a kubernetes cluster.
 1. DEPRECATED: Create a tanka environment.
 1. Bootstrap a new STELAR installation and prepare the cluster.
 1. Apply the environment to the cluster.

The steps are outlined below.

### Install Graphana Tanka and Jsonnet Bundler

Tanka is a tool for simplifying Kubernetes deployment and 
configuration. Tanka is open-source and is being used by Graphana 
Labs to manage their own clusters.

Tanka can be found in the following link from Graphana Labs 
[https://grafana.com/oss/tanka/](https://grafana.com/oss/tanka/).

Tanka uses the [Jsonnet bundler](https://github.com/jsonnet-bundler/jsonnet-bundler) for 
package management. Installation instructions for both tanka and jsonnet bundler can be found at https://tanka.dev/install.

Note: besides `tanka` and `jb`, other dependencies include 
 - `kubectl` to access some Kubernetes cluster
 - `helm` to download existing charts

### Update the Jsonnet packages in this repository.

Once jsonnet bundler is installed, please do
```
user% jb update
GET ...
...

user% tk tool charts vendor
{ ... 

```

This will make sure that you have all required Jsonnet libraries, as well
as charts.

### Access to a kubernetes cluster

The standard tool for Kubernetes cluster access is `kubectl`. Since a user may
have access to multiple clusters, `kubectl` configuration contains several 
**contexts**. These contexts can be seen by the following command
```
user% kubectl config get-contexts
CURRENT   NAME       CLUSTER    AUTHINFO   NAMESPACE
*         minikube   minikube   minikube   default
```
In the above example, there is a single context installed. The name of this
context is __minikube__.

### DEPRECATED/Use Bootstrap tool: Create a tanka environment

A tanka environment customizes the STELAR release to the individual deployment. For example, you may want to create a __stelar_devel__ 
environment as well as a __stelar_testing__ deployment on the same cluster.

A simple tanka environment can be created by the following command:
```
user% tk env add environments/stelar/my_env --namespace stelar --server-from-context minikube
```

This will create the environment on the Kubernetes cluster accessible
via the __minikube__ kubectl context.

### Bootstrap a new environment

Bootstrap creates a new installation of STELAR in a kubernetes cluster.
To do this, the __bootstrap__ tool generates a new Tanka environment and 
also initializes the kubernetes cluster.


### Apply an environment to the cluster

This can be achieved with the following command:
```
user% tk apply environments/stelar/my_env
```
A list of the full manifest (in YAML) is printed and there is a confirmation prompt. Typing __yes__ will perform the deployment. You can check that
everything is running by a command like
```
user% kubectl get pods --namespace stelar
```
which will hopefully show a number of pods in the RUNNING state.

### Deleting an environment from the cluster
```
user% tk delete environments/stelar/my_env
```


## Bootstrapping a new cluster

This is done using the bootstrap tool, which is executed as follows:
```
python test_boot.py -f  <bootstrap.yaml>
```

The '<bootstrap.yaml>' file is a yaml file that contains several details
pertaining to the new cluster. A sample file is shown below

```
env_name: "minikube.dev"
#define either "amazon" or "minikube"
platform: "minikube"
k8s_context: "minikube"
namespace: "stelar-dev"
author: "dpetrou@tuc.gr"
dns:
  - name: "minikube"
    scheme: "https"
    subdomains:
      - keycloak: "kc"
      - minio: "minio"
      - primary: "klms"
config:
  - smtp_server: "stelar.gr"
    smtp_port: "465"
    smtp_username: "info@stelar.gr"
    s3_console_url: "http://klms.minikube/s3/login"
secrets:
  - name: "postgresdb-secret"
    data:
      - password: "postgres"
  - name: "ckandb-secret"
    data:
      - password: "ckan"
  - name: "keycloakdb-secret"
    data:
      - password: "keycloak"
  - name: "datastoredb-secret"
    data:
      - password: "datastore"
  - name: "keycloakroot-secret"
    data:
      - password: "stelartuc"
  - name: "smtpapi-secret"
    data:
      - password: "t&0gc8Y04!@"
  - name: "ckanadmin-secret"
    data:
      - password: "stelar1234"
  - name: "minioroot-secret"
    data:
      - password: "stelartuc"
```

