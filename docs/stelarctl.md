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
| `ENV/` | One stelarctl-marked Tanka environment and deployment target, where `ENV` is the workspace-relative path passed to `lake add`. |
| `ENV/main.jsonnet` | Tanka entrypoint copied from the vendored STELAR deployment library. |
| `ENV/spec.json` | Tanka environment metadata. Carries the stelarctl lake marker. `lake create --context/--namespace` may populate deployment target fields; `lake bootstrap` fills missing target fields from kubeconfig and writes labels/annotations. |
| `ENV/product.json` | Validated product input copied into the environment. |
| `ENV/product_fullspec.json` | Fully defaulted product generated from the feature model. Jsonnet uses this as the deployment config inventory. |
| `ENV/manual_tls.yaml` | Optional operator-provided certificate directory mapping for manual TLS deployments. |

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
- `kubectl` provides the Kubernetes context and default namespace used by `lake bootstrap` when they are missing from `ENV/spec.json`.

`stelarctl` prepares inputs for those tools. It intentionally does not run
`tk apply` automatically.

## Minimal deployment workflow

Run these commands from any directory. Use `--workspace` when the workspace is
not the current directory.

```bash
stelarctl workspace init ./lake-workspace
cd ./lake-workspace
jb install
stelarctl lake add dev
stelarctl lake create --minimal dev --context my-kube-context --namespace stelar-dev
stelarctl lake check-cluster dev
stelarctl lake bootstrap dev
tk apply dev
```

The environment argument is a workspace-relative path. `dev` creates `dev/`; `lakes/prod` creates `lakes/prod/`.

## Command reference

```text
stelarctl workspace init WORKSPACE
    options: --force
stelarctl workspace info [WORKSPACE]
stelarctl lake add ENV
    options: --workspace WORKSPACE, --adopt-existing-main
stelarctl lake list
    options: --workspace WORKSPACE
stelarctl lake info ENV
    options: --workspace WORKSPACE
stelarctl lake remove ENV
    options: --workspace WORKSPACE, --yes
stelarctl lake create PRODUCT ENV
    options: --workspace WORKSPACE, --context CONTEXT, --namespace NAMESPACE
stelarctl lake create --minimal ENV
    options: --workspace WORKSPACE, --context CONTEXT, --namespace NAMESPACE,
             --manual-secrets, --infer-storage-from-cluster
stelarctl lake check-cluster ENV
    options: --workspace WORKSPACE, --context CONTEXT, --namespace NAMESPACE
stelarctl lake bootstrap ENV
    options: --workspace WORKSPACE, --skip-preflight
stelarctl lake manual-tls-template [OUTPUT]
    options: --force
```

## Commands

### `workspace init`

```bash
stelarctl workspace init WORKSPACE [--force]
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

### `workspace info`

```bash
stelarctl workspace info [WORKSPACE]
```

Prints read-only workspace state, including whether `jsonnetfile.json`, `lib/`,
and `vendor/` exist. It lists lake environments whose `spec.json` contains the
`metadata.annotations["stelar.eu/lake-environment"]: "true"` marker. For each
discovered lake environment, it shows
whether `main.jsonnet`, `spec.json`, `product.json`, and `product_fullspec.json`
are present.

`WORKSPACE` defaults to the current directory.

### `lake add`

```bash
stelarctl lake add ENV [--workspace WORKSPACE] [--adopt-existing-main]
```

Creates `ENV` relative to the workspace, copies `main_template.jsonnet`
from the vendored STELAR library as `main.jsonnet`, and creates a minimal `spec.json` skeleton.

This command expects `jb install` to have populated:

```text
vendor/github.com/stelar-eu/klms-deploy/lib/environment_templates/main_template.jsonnet
```

Existing marked environments are preserved for idempotent reruns. If `main.jsonnet` already exists but `spec.json` is missing or unmarked, the command stops to avoid silently adopting an arbitrary Tanka entrypoint. Use `--adopt-existing-main` only when that directory should be managed by stelarctl. Existing valid `spec.json` files are preserved and annotated with the stelarctl lake marker when explicit adoption is requested.

### `lake list`

```bash
stelarctl lake list [--workspace WORKSPACE]
```

Lists stelarctl-marked lake environments in the workspace. Ordinary Tanka directories are ignored unless their `spec.json` contains the lake marker. The output shows each environment path and whether generated product files are present.

### `lake info`

```bash
stelarctl lake info ENV [--workspace WORKSPACE]
```

Shows file-level state for one marked lake environment: path, `main.jsonnet`, `spec.json`, `product.json`, and `product_fullspec.json`.

### `lake remove`

```bash
stelarctl lake remove ENV [--workspace WORKSPACE] [--yes]
```

Deletes a marked lake environment directory. The command refuses unmarked directories, so it does not delete arbitrary workspace folders by typo. Without `--yes`, it asks for confirmation before deleting.

### `lake create`

```bash
stelarctl lake create PRODUCT ENV [--workspace WORKSPACE] [--context CONTEXT] [--namespace NAMESPACE]
stelarctl lake create --minimal ENV [--workspace WORKSPACE] [--context CONTEXT] [--namespace NAMESPACE] [--manual-secrets] [--infer-storage-from-cluster]
```

Creates product files inside an initialized lake environment.

The `PRODUCT ENV` mode loads an existing product JSON/YAML file, validates it against the feature model, and writes:

```text
ENV/product.json
ENV/product_fullspec.json
```

The `--minimal ENV` mode interactively creates a minimal product directly in the environment. The generated minimal product selects:

- required core components only
- PVC-backed PostgreSQL, MinIO, and Solr volumes
- nginx ingress
- no optional tools

It supports two TLS shapes:

- `SCHEME: http` with `ingress.tls: [no_tls]`
- `SCHEME: https` with `ingress.tls: [cert_manager]`

The minimal mode does not create manual TLS products. For manual TLS, write or edit a product that selects `manual_tls`, then use `lake manual-tls-template` to prepare the certificate input file.

When `http` is selected, `minio.INSECURE_MC_CLIENT` is forced to `true`. This is required because MinIO clients inside the deployment must use plain HTTP.

By default, `--minimal` creates cryptographically random secret values. The generated product/fullspec contain the values needed for `lake bootstrap` to create Kubernetes Secrets. Use `--manual-secrets` only when you want to type the secret values yourself instead of letting `stelarctl` generate them.

Use `--context CONTEXT` and/or `--namespace NAMESPACE` when you already know the deployment target. `lake create` writes whichever of those fields you provide into `ENV/spec.json`. Either flag may be omitted; `lake bootstrap` later fills only the missing field from kubeconfig.

Use `--infer-storage-from-cluster` when your Kubernetes user can read StorageClasses and you want the minimal-product prompt to prefill storage values from kubeconfig. Add `--context CONTEXT` to infer storage from a specific context and also record that context in `spec.json`.

Important validation rules:

- `SCHEME: http` requires `ingress.tls: [no_tls]`.
- `SCHEME: http` requires `minio.INSECURE_MC_CLIENT: "true"`.
- `SCHEME: https` requires one TLS mode: `cert_manager`, `manual_tls`, or `self_signed`.
- `manual_tls` requires `PRIMARY_TLS_SECRET_NAME`, `KEYCLOAK_TLS_SECRET_NAME`, `MINIO_API_TLS_SECRET_NAME`, and `REGISTRY_TLS_SECRET_NAME`.

If validation fails, no deployable fullspec should be treated as ready.

### `lake manual-tls-template`

```bash
stelarctl lake manual-tls-template [OUTPUT] [--force]
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
ENV/manual_tls.yaml
```

The YAML file does not define Kubernetes Secret names. Secret names come from
`product_fullspec.json` under `ingress.manual_tls`.

### `lake check-cluster`

```bash
stelarctl lake check-cluster ENV [--workspace WORKSPACE] [--context CONTEXT] [--namespace NAMESPACE]
```

Runs the bootstrap prerequisite checks without writing files and without
creating Kubernetes Secrets. The command validates that:

- `ENV` is a stelarctl-marked lake environment.
- `ENV/product_fullspec.json` exists and passes local deployment consistency checks.
- a Kubernetes context is available from `--context` or `ENV/spec.json`.
- a Kubernetes namespace is available from `--namespace` or `ENV/spec.json`.
- the selected cluster has the required namespace, StorageClasses, ingress, and TLS prerequisites.

Unlike `lake bootstrap`, this command does not infer missing context or namespace
from kubeconfig and does not update `spec.json`. If either target field is
missing, rerun with `--context` and/or `--namespace`, or persist the values with
`lake create --context ... --namespace ...`.

### `lake bootstrap`

```bash
stelarctl lake bootstrap ENV [--workspace WORKSPACE] [--skip-preflight]
```

Prepares the environment for Kubernetes:

1. Loads `product.json`, `product_fullspec.json`, and `spec.json`.
2. Reads `spec.contextNames` and `spec.namespace` when present.
3. If `spec.contextNames` is missing, records the active kubectl context.
4. If `spec.namespace` is missing, records the namespace configured on that context, or `default` when kubeconfig has none.
5. Updates `spec.json` with the completed target fields, labels, annotations, and Tanka metadata.
6. Validates scheme/TLS/MinIO consistency from the fullspec.
7. Runs read-only preflight checks unless `--skip-preflight` is used.
8. Creates missing product-derived Kubernetes Secrets.
9. Creates manual TLS Secrets if the fullspec selects `manual_tls`.

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
completes missing `spec.json` target fields, validates local config, and creates required Secrets.

Secrets are created only when missing. Existing Secrets are left untouched.

## TLS workflows

### Plain HTTP

Use `SCHEME: http` and `ingress.tls: [no_tls]`. MinIO insecure client mode must
be `true`. `lake create --minimal` enforces this automatically.

### HTTPS with cert-manager

Use `SCHEME: https`, `ingress.tls: [cert_manager]`, and provide
`ingress.cert_manager.ClusterIssuer`. `lake bootstrap` verifies cert-manager
and the ClusterIssuer during preflight.

### HTTPS with manual TLS

Use `SCHEME: https`, `ingress.tls: [manual_tls]`, and provide the four manual
TLS Secret names in the product. Then:

```bash
stelarctl lake manual-tls-template ENV/manual_tls.yaml
# edit ENV/manual_tls.yaml so each endpoint points to tls.crt/tls.key
stelarctl lake create PRODUCT ENV --context my-kube-context --namespace stelar-dev
stelarctl lake bootstrap ENV
```

`lake bootstrap` validates the certificate/key pairs before creating
Kubernetes TLS Secrets.

## Idempotency and safety

The commands are designed to be rerunnable:

- `workspace init` reuses directories and merges missing dependencies.
- `lake add` reuses directories and preserves already marked environments.
- `lake list` and `lake info` inspect marked lake environments without changing files.
- `lake remove` deletes one marked environment after confirmation, or immediately with `--yes`.
- `lake create` rewrites the generated product files for the environment.
- `lake check-cluster` validates prerequisites without writing files or creating Secrets.
- `lake bootstrap` completes missing `spec.json` target fields, validates prerequisites, and skips existing Secrets.

The main destructive option is `workspace init --force`, which rewrites
`jsonnetfile.json`.

## Troubleshooting

If `lake add` cannot find `main.jsonnet`, run `jb install` from the
workspace root and try again.

If `lake check-cluster` reports missing context or namespace, provide
`--context` and/or `--namespace` for the check, or persist those values with
`lake create --context ... --namespace ...`.

If preflight fails with an RBAC message, either use a Kubernetes identity with
read access to namespaces, StorageClasses, IngressClasses, pods, and cert-manager
resources, or rerun `lake bootstrap` with `--skip-preflight` and let `tk apply`
reveal cluster readiness problems later.

If manual TLS fails, check that `ENV/manual_tls.yaml` exists, that
each endpoint points to a directory, and that every directory contains a matching
PEM `tls.crt` and `tls.key` pair.

If an HTTP deployment renders HTTPS URLs or MinIO clients fail against HTTP
MinIO, inspect `product_fullspec.json` and verify `SCHEME` is `http`,
`ingress.tls` is `no_tls`, and `minio.INSECURE_MC_CLIENT` is `true`.

## Publishing the package

The PyPI workflow does not run on normal pushes to `main`. To publish a new
`stelar-deploy` package, tag the exact commit to release and push the tag:

```bash
git tag stelarctl-v0.1.12 <commit>
git push origin stelarctl-v0.1.12
```

The tag must use `stelarctl-vMAJOR.MINOR.PATCH` or
`stelarctl-vMAJOR.MINOR.PATCH.postN`. The workflow copies that version into
`pyproject.toml` before building and publishing the wheel.

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
deployments should use `stelarctl lake create --minimal` or `stelarctl lake
create PRODUCT ENV`, followed by `stelarctl lake bootstrap`.
