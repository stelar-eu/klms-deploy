# stelarctl

`stelarctl` prepares a STELAR KLMS lake deployment workspace before Kubernetes
manifests are rendered or applied with Tanka. It does not replace `jb`,
`jsonnet`, `tk`, or `kubectl`; it creates the STELAR-specific workspace files,
resolves products into fullspecs, checks cluster prerequisites, and creates the
bootstrap Secrets that are intentionally outside the Tanka render path.

## Mental Model

A workspace is a local deployment root. It contains `jsonnetfile.json`,
`vendor/` after `jb install`, and one or more lake environments.

A lake environment is a stelarctl-marked Tanka environment directory. It contains
`main.jsonnet`, `spec.json`, named product files, and optional TLS input files.
The local environment target is `spec.contextNames[0]` plus `spec.namespace`.

A product is the user input. A fullspec is the fully defaulted product produced
from the feature model. `lake create` writes both:

```text
ENV/<productName>.json
ENV/<productName>_fullspec.json
```

`spec.stelar.active_product` is only the local render selection consumed by
`main.jsonnet`. The cluster source of truth after bootstrap is the ConfigMap
`stelar-lake-state` in the target namespace. That ConfigMap stores the product
name, product input when available, and the deployed fullspec. If that ConfigMap
is absent, the namespace is not considered bootstrapped by stelarctl.

## Basic Workflow

```bash
stelarctl workspace init ./lake-workspace
cd ./lake-workspace
jb install
stelarctl lake add dev --context my-context --namespace stelar-dev
stelarctl lake create --minimal minimal dev --namespace stelar-dev
stelarctl lake verify dev
stelarctl lake bootstrap dev
tk apply dev
stelarctl lake status dev
```

The first created product is selected automatically. Use
`stelarctl lake switch PRODUCT_NAME ENV` to change the local render selection.
If the target namespace is already bootstrapped for another product, switch warns;
unbootstrap the namespace and rerun bootstrap before applying the switched product
to the same namespace.

## Commands

```text
stelarctl workspace init WORKSPACE [--force]
stelarctl workspace info [WORKSPACE]
stelarctl lake add ENV [--workspace WORKSPACE] [--context CONTEXT] [--namespace NAMESPACE] [--adopt-existing-main]
stelarctl lake list [--workspace WORKSPACE]
stelarctl lake info ENV [--workspace WORKSPACE]
stelarctl lake remove ENV [--workspace WORKSPACE] [--yes] [--force]
stelarctl lake create PRODUCT ENV [--workspace WORKSPACE] [--print-fullspec]
stelarctl lake create --minimal PRODUCT_NAME ENV [--workspace WORKSPACE] [--context CONTEXT] [--namespace NAMESPACE] [--custom-secret-names] [--infer-storage-from-cluster] [--print-fullspec]
stelarctl lake switch PRODUCT_NAME ENV [--workspace WORKSPACE]
stelarctl lake manual-tls-template [OUTPUT] [--force]
stelarctl lake verify ENV [--workspace WORKSPACE] [--context CONTEXT] [--namespace NAMESPACE]
stelarctl lake bootstrap ENV [--workspace WORKSPACE] [--skip-preflight] [--manual-secrets]
stelarctl lake status ENV [--workspace WORKSPACE] [--context CONTEXT] [--namespace NAMESPACE] [--wait --job-timeout SECONDS --poll-interval SECONDS]
stelarctl lake unbootstrap ENV [--workspace WORKSPACE] [--context CONTEXT] [--namespace NAMESPACE] [--yes]
```

## Command Behavior

`workspace init` creates or updates the workspace root and Jsonnet Bundler files.
Run `jb install` afterwards so `vendor/lib/...` exists.

`lake add` creates a marked Tanka environment. It copies the managed
`main_template.jsonnet` from `vendor/lib/environment_templates/` and creates or
marks `spec.json`. `--context` and `--namespace` write the initial target fields.

`lake create` resolves a product into named product/fullspec files. Minimal mode
prompts for a core-only product and never stores password values. Secret names
use defaults unless `--custom-secret-names` is used. Secret values are generated
at bootstrap time, unless `lake bootstrap --manual-secrets` is used.

`lake switch` updates `spec.stelar.active_product` and
`spec.stelar.current_product`. It does not create Secrets, run preflight, or
apply manifests.

`lake verify` is read-only. It checks the local active fullspec and cluster
prerequisites against the target context/namespace. It does not infer missing
target fields and does not write files.

`lake bootstrap` validates the active fullspec, fills missing context/namespace
from kubeconfig, updates Tanka metadata in `spec.json`, runs preflight checks,
creates product and manual-TLS Secrets, then writes `stelar-lake-state` in the
target namespace. If `stelar-lake-state` already exists, bootstrap stops. If all
or only some expected bootstrap Secrets exist while the ConfigMap is absent,
bootstrap stops because the namespace is inconsistent. If Secret reads are
blocked by RBAC, stelarctl warns and attempts creation; Kubernetes conflicts
still stop the command before ConfigMap state is recorded.

`lake status` is read-only and cluster-driven. It reads `stelar-lake-state`; if
the ConfigMap is absent it reports `not_bootstrapped`. If present, it reads the
stored fullspec, checks the corresponding bootstrap Secrets, and inspects the
expected Deployments, StatefulSets, and Jobs. `--wait` polls init Jobs until they
succeed or `--job-timeout` expires.

`lake unbootstrap` deletes bootstrap Secrets derived from the fullspec stored
in `stelar-lake-state`, then deletes the ConfigMap. If the ConfigMap is absent,
it falls back to local `spec.stelar.active_product` only as cleanup for failed
bootstraps that created Secrets before recording cluster state. It does not
delete Tanka-rendered resources; use `tk delete ENV` for those.

`lake remove` deletes the local marked environment directory after confirmation.
It refuses environments with an active product unless `--force` is supplied. Use
`tk delete ENV` and `lake unbootstrap ENV` before removing an environment that
has been applied or bootstrapped.

## Manual TLS

Manual TLS products must select `ingress.tls: [manual_tls]` and define the TLS
Secret-name attributes in the fullspec. Generate the input template with:

```bash
stelarctl lake manual-tls-template ENV/manual_tls.yaml
```

Edit each endpoint value so it points to a directory containing `tls.crt` and
`tls.key`. `lake bootstrap` validates the certificate/key pairs before creating
Kubernetes TLS Secrets.

## State Files

`ENV/spec.json` contains local Tanka environment metadata, the stelarctl lake
marker, optional context/namespace target fields, and the local active fullspec.
It should not contain bootstrap Secret values.

`stelar-lake-state` is the cluster-side bootstrap marker. It is created only
after bootstrap Secrets are successfully applied. It intentionally does not store
Secret values or Secret-name lists; Secret names are derived from the stored
fullspec when needed.
