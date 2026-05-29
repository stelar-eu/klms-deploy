# stelarctl

`stelarctl` prepares a STELAR KLMS lake deployment workspace before Kubernetes
manifests are rendered or applied with Tanka. It does not replace `jb`,
`jsonnet`, `tk`, or `kubectl`; it coordinates the STELAR-specific files and
cluster bootstrap steps around those tools.

The tool has three responsibilities:

- Create a workspace and Tanka environment structure.
- Validate a product specification and generate a fully resolved
  `product_fullspec.json`.
- Prepare cluster-specific metadata and Kubernetes Secrets before `tk apply`.

## Mental model

A deployment is organized around these files and directories:

| Item | Purpose |
| --- | --- |
| `workspace/` | Root directory for one operator-managed lake workspace. |
| `jsonnetfile.json` | Jsonnet Bundler dependency file used by `jb install`. |
| `vendor/` | Dependencies fetched by Jsonnet Bundler. Created by `jb install`, not by `stelarctl`. |
| `environments/<env>/` | One Tanka environment and deployment target. |
| `environments/<env>/main.jsonnet` | Tanka entrypoint copied from the vendored STELAR deployment library. |
| `environments/<env>/spec.json` | Tanka environment metadata. `init-lake cluster` updates context, namespace, labels, and annotations. |
| `environments/<env>/product.json` | Validated product input copied into the environment. |
| `environments/<env>/product_fullspec.json` | Fully defaulted product generated from the feature model. Jsonnet uses this as the deployment config inventory. |
| `environments/<env>/manual_tls.yaml` | Optional operator-provided certificate directory mapping for manual TLS deployments. |

`product.json` is the compact user-authored input. `product_fullspec.json` is
the expanded configuration after defaults and feature selections are resolved.
If you need to understand what configuration will be consumed by the render,
inspect `product_fullspec.json`.

## Installation

The intended installation path for operators is `pipx`:

```bash
pipx install stelar-deploy
stelarctl --help
```

`pipx` creates an isolated Python environment and exposes the `stelarctl`
console command on the user's `PATH`.

To update an existing installation:

```bash
pipx upgrade stelar-deploy
```

For local development from this repository:

```bash
pipx install --force .
stelarctl --help
```

## External tools

A normal deployment still uses the standard Jsonnet/Tanka tools:

- `jb` installs Jsonnet dependencies into `vendor/`.
- `jsonnet` evaluates the deployment library.
- `tk` renders and applies Tanka environments.
- `kubectl` provides the Kubernetes context used by `init-lake cluster`.

`stelarctl` prepares inputs for those tools. It intentionally does not run
`tk apply` automatically.

## Minimal deployment workflow

Run these commands from any directory. Use `--workspace` when the workspace is
not the current directory.

```bash
stelarctl init-lake workspace ./lake-workspace
cd ./lake-workspace
jb install
stelarctl init-lake environment dev
stelarctl product init-minimal product.yaml --generate-secret-values
stelarctl product generate product.yaml dev
stelarctl init-lake cluster dev --context my-kube-context
tk apply environments/dev
```

The environment argument accepts either `dev` or `environments/dev`.

## Command reference

```text
stelarctl init-lake workspace WORKSPACE
    options: --force
stelarctl init-lake environment ENV
    options: --workspace WORKSPACE
stelarctl init-lake cluster ENV
    options: --workspace WORKSPACE, --context CONTEXT, --skip-preflight
stelarctl product init-minimal [OUTPUT]
    options: --generate-secret-values, --secret-values-output FILE,
             --infer-storage-from-cluster, --context CONTEXT, --force
stelarctl product init-manual-tls [OUTPUT]
    options: --force
stelarctl product generate PRODUCT ENV
    options: --workspace WORKSPACE
```

## Commands

### `init-lake workspace`

```bash
stelarctl init-lake workspace WORKSPACE [--force]
```

Creates the workspace root and writes the packaged `jsonnetfile.json` template.
If `jsonnetfile.json` already exists, the command merges the required STELAR
Jsonnet dependency when possible and preserves existing dependency pins.

After this command, run:

```bash
cd WORKSPACE
jb install
```

`jb install` is what creates `vendor/`. `stelarctl` does not vendor dependencies
by itself.

Use `--force` only when you intentionally want to rewrite `jsonnetfile.json`
from the packaged template.

### `init-lake environment`

```bash
stelarctl init-lake environment ENV [--workspace WORKSPACE]
```

Creates `environments/ENV`, copies `main.jsonnet` from the vendored STELAR
library, and creates a minimal `spec.json` skeleton.

This command expects `jb install` to have populated:

```text
vendor/github.com/stelar-eu/klms-deploy/lib/environment_templates/main.jsonnet
```

Existing `main.jsonnet` and `spec.json` files are not overwritten.

### `product init-minimal`

```bash
stelarctl product init-minimal [OUTPUT] [--generate-secret-values] [--secret-values-output FILE] [--infer-storage-from-cluster] [--context CONTEXT] [--force]
```

Interactively creates a minimal product spec. The generated product selects:

- required core components only
- PVC-backed PostgreSQL, MinIO, and Solr volumes
- nginx ingress
- no optional tools

It supports two TLS shapes:

- `SCHEME: http` with `ingress.tls: [no_tls]`
- `SCHEME: https` with `ingress.tls: [cert_manager]`

The minimal generator does not create manual TLS products. For manual TLS, write
or edit a product that selects `manual_tls`, then use `product init-manual-tls`
to prepare the certificate input file.

When `http` is selected, `minio.INSECURE_MC_CLIENT` is forced to `true`. This is
required because MinIO clients inside the deployment must use plain HTTP.

Use `--generate-secret-values` to let `stelarctl` create cryptographically
random secret values. The product contains the values needed for validation, and
a sidecar file such as `product.secrets.yaml` is written for operator reference.
Use `--secret-values-output FILE` to choose a different sidecar path. Store that
sidecar file securely.

Use `--infer-storage-from-cluster` when your Kubernetes user can read
StorageClasses and you want the command to prefill storage values from the
active kubectl context. Add `--context CONTEXT` to infer from a specific context.
Use `--force` to overwrite existing output files.

### `product init-manual-tls`

```bash
stelarctl product init-manual-tls [OUTPUT] [--force]
```

Writes a template with endpoint-to-directory mappings. `OUTPUT` defaults to
`manual_tls.yaml`. Use `--force` to overwrite an existing file.

```yaml
manual_tls:
  primary: ./certs/primary
  keycloak: ./certs/keycloak
  minio_api: ./certs/minio-api
  registry: ./certs/registry
```

Edit each value so it points to a directory containing:

```text
tls.crt
tls.key
```

Then place the edited file at:

```text
environments/ENV/manual_tls.yaml
```

The YAML file does not define Kubernetes Secret names. Secret names come from
`product_fullspec.json` under `ingress.manual_tls`.

### `product generate`

```bash
stelarctl product generate PRODUCT ENV [--workspace WORKSPACE]
```

Loads a product JSON or YAML file, validates it against the feature model, and
writes:

```text
environments/ENV/product.json
environments/ENV/product_fullspec.json
```

Important validation rules:

- `SCHEME: http` requires `ingress.tls: [no_tls]`.
- `SCHEME: http` requires `minio.INSECURE_MC_CLIENT: "true"`.
- `SCHEME: https` requires one TLS mode: `cert_manager`, `manual_tls`, or `self_signed`.
- `manual_tls` requires `PRIMARY_TLS_SECRET_NAME`, `KEYCLOAK_TLS_SECRET_NAME`, `MINIO_API_TLS_SECRET_NAME`, and `REGISTRY_TLS_SECRET_NAME`.

If validation fails, no deployable fullspec should be treated as ready.

### `init-lake cluster`

```bash
stelarctl init-lake cluster ENV [--workspace WORKSPACE] [--context CONTEXT] [--skip-preflight]
```

Prepares the environment for the selected Kubernetes cluster:

1. Loads `product.json` and `product_fullspec.json`.
2. Resolves the explicit `--context` or active kubectl context.
3. Updates `spec.json` with context, namespace, labels, annotations, and Tanka metadata.
4. Validates scheme/TLS/MinIO consistency from the fullspec.
5. Runs read-only preflight checks unless `--skip-preflight` is used.
6. Creates missing product-derived Kubernetes Secrets.
7. Creates manual TLS Secrets if the fullspec selects `manual_tls`.

Current preflight checks verify:

- configured namespace exists
- configured dynamic storage class exists
- configured provisioning storage class exists
- `nginx` IngressClass exists
- a ready ingress-nginx controller pod exists
- for cert-manager TLS, cert-manager CRDs exist
- for cert-manager TLS, cert-manager deployments are ready
- for cert-manager TLS, the configured ClusterIssuer exists and is Ready

If the Kubernetes user lacks RBAC access for a read-only preflight check,
`stelarctl` stops and tells the user to rerun with `--skip-preflight`. That flag
skips only read-only prerequisite checks. It still loads the Kubernetes context,
updates `spec.json`, validates local config, and creates required Secrets.

Secrets are created only when missing. Existing Secrets are left untouched.

## TLS workflows

### Plain HTTP

Use `SCHEME: http` and `ingress.tls: [no_tls]`. MinIO insecure client mode must
be `true`. `product init-minimal` enforces this automatically.

### HTTPS with cert-manager

Use `SCHEME: https`, `ingress.tls: [cert_manager]`, and provide
`ingress.cert_manager.ClusterIssuer`. `init-lake cluster` verifies cert-manager
and the ClusterIssuer during preflight.

### HTTPS with manual TLS

Use `SCHEME: https`, `ingress.tls: [manual_tls]`, and provide the four manual
TLS Secret names in the product. Then:

```bash
stelarctl product init-manual-tls environments/ENV/manual_tls.yaml
# edit environments/ENV/manual_tls.yaml so each endpoint points to tls.crt/tls.key
stelarctl init-lake cluster ENV --context my-kube-context
```

`init-lake cluster` validates the certificate/key pairs before creating
Kubernetes TLS Secrets.

## Idempotency and safety

The commands are designed to be rerunnable:

- `init-lake workspace` reuses directories and merges missing dependencies.
- `init-lake environment` reuses directories and preserves existing files.
- `product generate` rewrites the generated product files for the environment.
- `init-lake cluster` updates `spec.json`, validates prerequisites, and skips existing Secrets.

The main destructive option is `init-lake workspace --force`, which rewrites
`jsonnetfile.json`.

## Troubleshooting

If `init-lake environment` cannot find `main.jsonnet`, run `jb install` from the
workspace root and try again.

If preflight fails with an RBAC message, either use a Kubernetes identity with
read access to namespaces, StorageClasses, IngressClasses, pods, and cert-manager
resources, or rerun with `--skip-preflight` and let `tk apply` reveal cluster
readiness problems later.

If manual TLS fails, check that `environments/ENV/manual_tls.yaml` exists, that
each endpoint points to a directory, and that every directory contains a matching
PEM `tls.crt` and `tls.key` pair.

If an HTTP deployment renders HTTPS URLs or MinIO clients fail against HTTP
MinIO, inspect `product_fullspec.json` and verify `SCHEME` is `http`,
`ingress.tls` is `no_tls`, and `minio.INSECURE_MC_CLIENT` is `true`.

## Code layout

The CLI is split so future commands can be added without expanding the entrypoint:

- `src/stelar/deploy/cli.py`: stable console-script entrypoint
- `src/stelar/deploy/cli_app.py`: Typer app construction
- `src/stelar/deploy/cli_help.py`: centralized user-facing CLI help text
- `src/stelar/deploy/cli_handlers/`: CLI adapters and command registration
- `src/stelar/deploy/operations/`: testable command business logic
- `src/stelar/deploy/templates/`: packaged templates copied or emitted by commands

Business logic should not print directly. Add user-facing output through a CLI
adapter or progress reporter so behavior remains testable without a CLI runner.

To add a future command group:

1. Add testable business logic under `src/stelar/deploy/operations/`.
2. Add a Typer adapter under `src/stelar/deploy/cli_handlers/`.
3. Register the adapter in `src/stelar/deploy/cli_handlers/__init__.py`.
4. Keep Kubernetes, Tanka, and filesystem behavior outside the CLI adapter when possible.
5. Add unit tests for business behavior and focused CLI tests for argument/help/progress output.

## Legacy bootstrap script

The old bootstrap script has moved to `legacy/bootstrap.py`. It is kept only for
older installations that still depend on the previous `bootstrap.yaml` flow. New
deployments should use `stelarctl product init-minimal`, `stelarctl product
generate`, and `stelarctl init-lake cluster`.
