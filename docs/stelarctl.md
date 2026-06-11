# stelarctl

`stelarctl` prepares a STELAR KLMS lake deployment workspace before Kubernetes
manifests are rendered or applied with Tanka. It does not replace `jb`,
`jsonnet`, `tk`, or `kubectl`; it coordinates the STELAR-specific files and
cluster bootstrap steps around those tools.

The tool has three responsibilities:

- Create a workspace and Tanka environment structure.
- Validate a product specification and record a fully resolved fullspec at
  `spec.stelar.active_product`.
- Prepare cluster-specific metadata and Kubernetes Secrets before `tk apply`.

## Mental model

A deployment is organized around these files and directories:

| Item | Purpose |
| --- | --- |
| `workspace/` | Root directory for one operator-managed lake workspace. |
| `jsonnetfile.json` | Jsonnet Bundler dependency file used by `jb install`. |
| `vendor/` | Dependencies fetched by Jsonnet Bundler. Created by `jb install`, not by `stelarctl`. |
| `ENV/` | One stelarctl-marked Tanka environment and deployment target, where `ENV` is the workspace-relative path passed to `lake add`. |
| `ENV/main.jsonnet` | Tanka entrypoint copied from the vendored STELAR deployment library. It imports `spec.json` and passes `spec.stelar.active_product` to `build_lake`. |
| `ENV/spec.json` | Tanka environment metadata. Carries the stelarctl lake marker, activation state at `spec.stelar.active_product`, optional target fields, optional bootstrap state at `spec.stelar.bootstrapped_product`, and Tanka labels/annotations. |
| `ENV/<productName>.json` | Named validated product input copied into the environment. |
| `ENV/<productName>_fullspec.json` | Named fully defaulted product generated from the feature model. |
| `ENV/manual_tls.yaml` | Optional operator-provided certificate directory mapping for manual TLS deployments. |

Each created product is stored as `<productName>.json` and
`<productName>_fullspec.json`. `lake activate PRODUCT_NAME ENV` reads those
named artifacts and stores the selected fullspec in `ENV/spec.json` at
`spec.stelar.active_product` and records the name in
`spec.stelar.active_product_name`. `main.jsonnet`, `lake verify`, and
`lake bootstrap` consume that active fullspec. After a successful bootstrap,
`spec.stelar.bootstrapped_product` records the product name, target hash, and
Secret names used for bootstrap-state checks.

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
stelarctl lake add dev --context my-kube-context --namespace stelar-dev
stelarctl lake create --minimal minimal dev --namespace stelar-dev
stelarctl lake verify dev --context my-kube-context --namespace stelar-dev
stelarctl lake bootstrap dev
tk apply dev
stelarctl lake status dev
```

The first created product is activated automatically. Run
`stelarctl lake activate PRODUCT_NAME ENV` only when switching to another
generated product or after regenerating the active product.

The environment argument is a workspace-relative path. `dev` creates `dev/`; `lakes/prod` creates `lakes/prod/`.

## Command reference

```text
stelarctl workspace init WORKSPACE
    options: --force
stelarctl workspace info [WORKSPACE]
stelarctl lake add ENV
    options: --workspace WORKSPACE, --context CONTEXT, --namespace NAMESPACE,
             --adopt-existing-main
stelarctl lake list
    options: --workspace WORKSPACE
stelarctl lake info ENV
    options: --workspace WORKSPACE
stelarctl lake remove ENV
    options: --workspace WORKSPACE, --yes, --force
stelarctl lake create PRODUCT ENV
    options: --workspace WORKSPACE
stelarctl lake create --minimal PRODUCT_NAME ENV
    options: --workspace WORKSPACE, --context CONTEXT, --namespace NAMESPACE,
             --manual-secrets, --infer-storage-from-cluster
stelarctl lake activate PRODUCT_NAME ENV
    options: --workspace WORKSPACE
stelarctl lake manual-tls-template [OUTPUT]
    options: --force
stelarctl lake verify ENV
    options: --workspace WORKSPACE, --context CONTEXT, --namespace NAMESPACE
stelarctl lake status ENV
    options: --workspace WORKSPACE, --context CONTEXT, --namespace NAMESPACE,
             --wait, --job-timeout SECONDS, --poll-interval SECONDS
stelarctl lake purge-secrets ENV
    options: --workspace WORKSPACE, --context CONTEXT, --namespace NAMESPACE, --yes
stelarctl lake bootstrap ENV
    options: --workspace WORKSPACE, --skip-preflight
```

## Commands

### `workspace init`

```bash
stelarctl workspace init WORKSPACE [--force]
```

Creates the workspace root, ensures local `lib/` exists, and writes the packaged `jsonnetfile.json` template.
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
whether `main.jsonnet`, `spec.json`, an active product, and named generated products
are present.

`WORKSPACE` defaults to the current directory.

### `lake add`

```bash
stelarctl lake add ENV [--workspace WORKSPACE] [--context CONTEXT] [--namespace NAMESPACE] [--adopt-existing-main]
```

Creates `ENV` relative to the workspace, copies `main_template.jsonnet`
from the vendored STELAR library as `main.jsonnet`, and creates a minimal `spec.json` skeleton. Pass `--context` and/or `--namespace` to record the initial Kubernetes target in `spec.json` before the first successful bootstrap; omitted target fields remain absent and can be inferred by `lake bootstrap` before bootstrap state is recorded. After `spec.stelar.bootstrapped_product` exists, `lake add` refuses to run. Restoring `spec.contextNames` or `spec.namespace` after bootstrap is a manual `spec.json` repair.

This command expects `jb install` to have populated:

```text
vendor/lib/environment_templates/main_template.jsonnet
```

Existing marked environments are preserved for idempotent pre-bootstrap reruns. If `main.jsonnet` already exists but `spec.json` is missing or unmarked, the command stops to avoid silently taking over an arbitrary Tanka entrypoint.

`--adopt-existing-main` is the explicit takeover switch for that case. It keeps the existing `main.jsonnet` only if it matches the managed stelarctl `main_template.jsonnet`, creates or marks `spec.json` with the stelarctl lake marker, and treats the directory as a stelarctl-managed lake environment from then on. Custom Tanka entrypoints are rejected because they may render resources unrelated to `spec.stelar.active_product`.

### `lake list`

```bash
stelarctl lake list [--workspace WORKSPACE]
```

Lists stelarctl-marked lake environments in the workspace. Ordinary Tanka directories are ignored unless their `spec.json` contains the lake marker. The output shows each environment path and whether generated product files are present.

### `lake info`

```bash
stelarctl lake info ENV [--workspace WORKSPACE]
```

Shows file-level state for one marked lake environment: path, `main.jsonnet`, `spec.json`, active product state, and generated product names.

### `lake remove`

```bash
stelarctl lake remove ENV [--workspace WORKSPACE] [--yes] [--force]
```

Deletes a marked lake environment directory. The command refuses unmarked directories, so it does not delete arbitrary workspace folders by typo. Without `--yes`, it asks for confirmation before deleting. It also refuses environments that still contain an active product or recorded bootstrap state unless `--force` is supplied. Use `--force` only after `tk delete ENV` and, when bootstrap state exists, `stelarctl lake purge-secrets ENV`, or when you intentionally want to discard local cleanup metadata.

### `lake create`

```bash
stelarctl lake create PRODUCT ENV [--workspace WORKSPACE]
stelarctl lake create --minimal PRODUCT_NAME ENV [--workspace WORKSPACE] [--context CONTEXT] [--namespace NAMESPACE] [--manual-secrets] [--infer-storage-from-cluster]
```

Creates product files inside an initialized lake environment.

The `PRODUCT ENV` mode loads an existing product JSON/YAML file, validates it against the feature model, and derives `productName` from the input filename stem. It writes:

```text
ENV/<productName>.json
ENV/<productName>_fullspec.json
```

The `--minimal PRODUCT_NAME ENV` mode interactively creates a named minimal product directly in the environment. `PRODUCT_NAME` may be given as `name` or `name.json`. The generated minimal product selects:

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

`lake create` activates the generated product only when the environment has no active product yet. Later creations do not change the active product; use `lake activate PRODUCT_NAME ENV` to switch the deployable product. If you regenerate the same product name that is already active, the command warns when `spec.stelar.active_product` still points to the previous fullspec. In minimal mode, `--namespace` and `--context` write deployment target fields to `ENV/spec.json`; `--context` is also used with `--infer-storage-from-cluster` to inspect StorageClasses from a specific kube context. Product/fullspec files do not contain the Kubernetes namespace.

Important validation rules:

- `SCHEME: http` requires `ingress.tls: [no_tls]`.
- `SCHEME: http` requires `minio.INSECURE_MC_CLIENT: "true"`.
- `SCHEME: https` requires one TLS mode: `cert_manager` or `manual_tls`.
- `manual_tls` requires `PRIMARY_TLS_SECRET_NAME`, `KEYCLOAK_TLS_SECRET_NAME`, `MINIO_API_TLS_SECRET_NAME`, and `REGISTRY_TLS_SECRET_NAME`.

If validation fails, no deployable fullspec should be treated as ready.


### `lake activate`

```bash
stelarctl lake activate PRODUCT_NAME ENV [--workspace WORKSPACE]
```

Selects one generated product as the active deployable product. `PRODUCT_NAME`
may be given as `name` or `name.json`. The command reads:

```text
ENV/<productName>.json
ENV/<productName>_fullspec.json
```

Then it validates the fullspec and writes it into:

```text
ENV/spec.json -> spec.stelar.active_product
ENV/spec.json -> spec.stelar.active_product_name
```

Activation does not create Secrets or run `tk apply`. If `spec.json` already
has a context and namespace, it tries to inspect bootstrap Secrets before
switching. Existing bootstrap Secrets or RBAC/API failures are reported as
warnings and activation still proceeds. If the recorded bootstrap target hash no
longer matches `spec.contextNames/spec.namespace`, activation is refused until
the original target is restored. Re-activating the same already bootstrapped
product is reported as informational output, not a warning.

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
`spec.stelar.active_product` under `ingress.manual_tls`.

### `lake verify`

```bash
stelarctl lake verify ENV [--workspace WORKSPACE] [--context CONTEXT] [--namespace NAMESPACE]
```

Verifies that a lake environment is ready for bootstrap/apply against a
Kubernetes cluster. The command performs read-only checks only and validates that:

- `ENV` is a stelarctl-marked lake environment.
- `ENV/spec.json` defines `spec.stelar.active_product`, and it passes local deployment consistency checks.
- a Kubernetes context is available from `--context` or `ENV/spec.json`.
- a Kubernetes namespace is available from `--namespace` or `ENV/spec.json`.
- the selected cluster has the required namespace, StorageClasses, ingress, and TLS prerequisites.

Unlike `lake bootstrap`, this command does not infer missing context or namespace
from kubeconfig and does not update `spec.json`. If either target field is
missing, rerun with `--context` and/or `--namespace`, or let `lake bootstrap`
infer and persist the values. After `spec.stelar.bootstrapped_product` exists,
`--context` and `--namespace` overrides are rejected; the stored `spec.json`
target must be restored manually and must match the recorded target hash.

### `lake status`

```bash
stelarctl lake status ENV [--workspace WORKSPACE] [--context CONTEXT] [--namespace NAMESPACE] [--wait --job-timeout SECONDS --poll-interval SECONDS]
```

Inspects the current cluster state for one lake environment without mutating
files or Kubernetes resources. The command requires `spec.stelar.active_product`
to pass local scheme/TLS and secret-value validation, plus a target
context/namespace from `spec.json` or explicit flags. Missing target
fields are not inferred or written.

Bootstrap state is inferred from `spec.stelar.bootstrapped_product.secret_names`
when present, otherwise from the required Secret names in the active fullspec.
After bootstrap state exists, `--context` and `--namespace` overrides are
rejected; the stored `spec.json` target must match the recorded hash or the
command stops until the original target is restored. States:

- `bootstrapped`: every required bootstrap Secret exists.
- `not_bootstrapped`: none of the required bootstrap Secrets exist.
- `partial`: only some required bootstrap Secrets exist.
- `unknown`: RBAC or an API error prevents inspection.

Deployment state is inferred from the selected fullspec components. `stelarctl`
checks the expected Deployments, StatefulSets, and init Jobs for those
components. By default, `lake status` performs one snapshot check. Use `--wait`
with required `--job-timeout` and positive `--poll-interval` values when init Jobs should
be polled until they complete, so transient failed attempts are not treated as
final failure too early. Components without native workload mappings, such as
placeholder Prometheus/Grafana entries or the Helm-backed Airflow entry, are
reported as `unchecked`.

### `lake purge-secrets`

```bash
stelarctl lake purge-secrets ENV [--workspace WORKSPACE] [--context CONTEXT] [--namespace NAMESPACE] [--yes]
```

Deletes only the Kubernetes Secrets created by `lake bootstrap`. When
`spec.stelar.bootstrapped_product` exists, it uses the recorded Secret names,
rejects `--context`/`--namespace` overrides, and requires the stored `spec.json`
target to match the recorded hash. Otherwise it falls back to the active fullspec.
It does not delete Tanka-rendered resources such as Deployments,
StatefulSets, Jobs, Services, PVCs, Ingresses, or ConfigMaps. Use `tk delete
ENV` for rendered manifests, then use `lake purge-secrets ENV` when you also
want to remove bootstrap Secrets.

The command requires a target context/namespace from `spec.json` or explicit
flags. Missing Secrets are reported as already missing. RBAC delete failures
stop the command with the Secret name and namespace. Without `--yes`, it asks
for confirmation before deleting.

### `lake bootstrap`

```bash
stelarctl lake bootstrap ENV [--workspace WORKSPACE] [--skip-preflight]
```

Prepares the environment for Kubernetes:

1. Loads `spec.json` and reads `spec.stelar.active_product`.
2. Reads `spec.contextNames` and `spec.namespace` when present.
3. If no `spec.stelar.bootstrapped_product` exists yet and `spec.contextNames` is missing, records the active kubectl context.
4. If no `spec.stelar.bootstrapped_product` exists yet and `spec.namespace` is missing, records the namespace configured on that context, or `default` when kubeconfig has none.
5. If `spec.stelar.bootstrapped_product` already exists, refuses to infer missing target fields; restore the recorded `spec.contextNames` and `spec.namespace` first.
6. Updates `spec.json` with the completed target fields, labels, annotations, and Tanka metadata.
7. Validates scheme/TLS/MinIO consistency from the fullspec.
8. Verifies that any existing `spec.stelar.bootstrapped_product` target hash matches the stored context/namespace.
9. Runs read-only preflight checks unless `--skip-preflight` is used.
10. Checks whether the required bootstrap Secrets already exist.
11. Creates missing Kubernetes Secrets from the active fullspec config.
12. Creates manual TLS Secrets if the fullspec selects `manual_tls`.
13. Records `spec.stelar.bootstrapped_product` with the product name, target hash, and bootstrap Secret names.

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

Before creating Secrets, `lake bootstrap` checks the recorded bootstrap Secret names when `spec.stelar.bootstrapped_product` exists, otherwise the required Secret names for the active fullspec. If every required Secret already exists, the command stops and reports that bootstrap appears to have already run. If only some required Secrets exist, the command stops because the namespace is partially bootstrapped and should be inspected or cleaned up before retrying. If RBAC blocks Secret reads, `stelarctl` warns that it cannot verify bootstrap state and attempts Secret creation directly; Kubernetes `409 Conflict` responses still leave existing Secrets untouched. If the current context/namespace target no longer matches the recorded target hash, the command stops before cluster mutation.

## TLS workflows

### Plain HTTP

Use `SCHEME: http` and `ingress.tls: [no_tls]`. MinIO insecure client mode must
be `true`. `lake create --minimal PRODUCT_NAME ENV` enforces this automatically.

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
stelarctl lake create PRODUCT ENV
stelarctl lake activate PRODUCT_NAME ENV
stelarctl lake bootstrap ENV
```

`lake bootstrap` validates the certificate/key pairs before creating
Kubernetes TLS Secrets.

## Idempotency and safety

The commands are designed to be rerunnable:

- `workspace init` reuses directories and merges missing dependencies.
- `lake add` reuses directories and preserves already marked environments before bootstrap state exists. It can write initial context/namespace fields before bootstrap, but refuses to run after `spec.stelar.bootstrapped_product` is recorded.
- `lake list` and `lake info` inspect marked lake environments without changing files.
- `lake remove` deletes one marked environment after confirmation, or immediately with `--yes`, but refuses active or bootstrapped environments unless `--force` is supplied.
- `lake create` rewrites named generated product files for the environment.
- `lake activate` updates `spec.stelar.active_product`.
- `lake verify` validates prerequisites without writing files or creating Secrets.
- `lake status` inspects bootstrap Secrets and selected-component workloads without writing files or creating resources.
- `lake purge-secrets` deletes only bootstrap Secrets created outside Tanka and skips already missing Secrets.
- `lake bootstrap` completes missing `spec.json` target fields only before the first recorded bootstrap, validates prerequisites, stops when all or only some required bootstrap Secrets already exist, creates Secrets only from a clean bootstrap state, and records `spec.stelar.bootstrapped_product` with product name and target hash.

The destructive commands are `lake remove`, `lake purge-secrets`, and
`workspace init --force`. `lake remove --force` can discard local cleanup metadata, `lake remove` affects local environment files,
`lake purge-secrets` affects Kubernetes Secrets in the selected namespace, and
`workspace init --force` rewrites
`jsonnetfile.json`.

## Troubleshooting

If `lake add` cannot find `main.jsonnet`, run `jb install` from the
workspace root and try again.

If `lake verify` reports missing context or namespace, provide
`--context` and/or `--namespace` for the check, or let `lake bootstrap` infer
and persist those values.

If preflight fails with an RBAC message, either use a Kubernetes identity with
read access to namespaces, StorageClasses, IngressClasses, pods, and cert-manager
resources, or rerun `lake bootstrap` with `--skip-preflight` and let `tk apply`
reveal cluster readiness problems later.

If manual TLS fails, check that `ENV/manual_tls.yaml` exists, that
each endpoint points to a directory, and that every directory contains a matching
PEM `tls.crt` and `tls.key` pair.

If an HTTP deployment renders HTTPS URLs or MinIO clients fail against HTTP
MinIO, inspect `spec.stelar.active_product` and verify `SCHEME` is `http`,
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
`pyproject.toml` before building and publishing the wheel. PyPI versions are
immutable: if the same `stelarctl-v...` version was already uploaded, the
publish job fails with a file-already-exists error. Use a new patch version
or a `.postN` tag for every new package upload.

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
deployments should use `stelarctl lake create --minimal PRODUCT_NAME ENV` or
`stelarctl lake create PRODUCT ENV`, followed by `stelarctl lake activate` and
`stelarctl lake bootstrap`.
