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

The supported deployment flow uses `stelarctl`, Jsonnet Bundler (`jb`), Tanka
(`tk`), and `kubectl`. The legacy bootstrap script has been moved to
`legacy/bootstrap.py` and is kept only as historical reference for older
installations.

The deployment flow is:

1. Install `stelarctl`, Tanka, Jsonnet Bundler, and `kubectl`.
2. Initialize a lake workspace.
3. Run `jb install` to fetch the vendored STELAR deployment library and Jsonnet dependencies.
4. Initialize a Tanka environment in the workspace.
5. Generate or provide a product spec.
6. Resolve the product spec into `product_fullspec.json`.
7. Prepare the cluster metadata and required secrets.
8. Apply the rendered manifests with Tanka.

### Install tooling

Install `stelarctl` with `pipx`:

```bash
pipx install stelar-deploy
stelarctl --help
```

Tanka and Jsonnet Bundler installation instructions are available from the
Tanka documentation: https://tanka.dev/install.

You also need `kubectl` configured with access to the target Kubernetes cluster.

### Initialize a workspace

A workspace is the deployable directory that contains the Jsonnet Bundler files,
vendored libraries, and one or more deployment environments.

```bash
stelarctl init-lake workspace ./lake-workspace
cd ./lake-workspace
jb install
```

`jb install` populates `vendor/` from `jsonnetfile.json`. The packaged template
fetches the STELAR deployment library from the `lib` subdirectory of the
`stelar-eu/klms-deploy` repository.

### Initialize an environment

Create an environment under `environments/`:

```bash
stelarctl init-lake environment dev --workspace .
```

This creates:

```text
environments/dev/main.jsonnet
environments/dev/spec.json
```

### Create a product spec

For a minimal deployment, use the interactive generator. It supports `http`
with `no_tls` and `https` with `cert_manager`; it does not generate manual TLS
products. When `http` is selected, `INSECURE_MC_CLIENT` is forced to `true`:

```bash
stelarctl product init-minimal product.yaml --generate-secret-values
```

When `--generate-secret-values` is used, `stelarctl` also writes a sidecar file
containing the generated values, for example:

```text
product.secrets.yaml
```

Store that file securely. It contains secret values.

If the operator has permission to read StorageClasses from the active Kubernetes
context, storage values can be inferred:

```bash
stelarctl product init-minimal product.yaml \
  --generate-secret-values \
  --infer-storage-from-cluster
```

### Resolve the product into a fullspec

```bash
stelarctl product generate product.yaml dev --workspace .
```

This writes:

```text
environments/dev/product.json
environments/dev/product_fullspec.json
```

For manually provisioned TLS, select `ingress.tls: [manual_tls]` in the product
and provide the four `ingress.manual_tls` secret-name attributes for the primary,
Keycloak, MinIO API, and registry hosts. To create the required input file that
lets `init-lake cluster` apply those secrets, run:

```bash
stelarctl product init-manual-tls environments/dev/manual_tls.yaml
```

Edit each endpoint value in that file to point to a directory containing
`tls.crt` and `tls.key`. The command only writes the YAML sample; it does not
create certificate directories.

### Prepare cluster metadata and secrets

```bash
stelarctl init-lake cluster dev --workspace . --context my-kube-context
```

By default this runs read-only prerequisite checks before creating missing
secrets. If those checks fail because the current Kubernetes user lacks RBAC
permissions to inspect cluster resources, rerun with:

```bash
stelarctl init-lake cluster dev --workspace . --context my-kube-context --skip-preflight
```

`--skip-preflight` skips only read-only prerequisite checks. It still loads the
Kubernetes context, updates `spec.json`, and creates required secrets.

### Apply an environment to the cluster

```bash
tk apply environments/dev
```

Tanka prints the rendered manifest and asks for confirmation before applying it.
After deployment, inspect the namespace with `kubectl`, for example:

```bash
kubectl get pods --namespace stelar-dev
```

### Delete an environment from the cluster

```bash
tk delete environments/dev
```

## Legacy bootstrap script

The previous bootstrap script is no longer part of the packaged `stelarctl`
module. It has been moved to:

```text
legacy/bootstrap.py
```

Use it only when maintaining an older installation that still depends on the old
`bootstrap.yaml` flow. New deployments should use the `stelarctl` workflow above.
