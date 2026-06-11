# stelarctl Behavior Review

This file describes the current intended behavior of `stelarctl` as implemented in this working tree. It is written as a review contract: if the implementation behaves differently from this file, either the code or this file should change.

## Mental Model

`stelarctl` prepares a STELAR KLMS lake deployment workspace. It does not replace Jsonnet Bundler, Tanka, kubectl, or the Kubernetes cluster. It creates and validates local deployment files, records the selected product fullspec, performs optional read-only cluster checks, and creates bootstrap Secrets that Tanka-rendered workloads later consume.

A workspace is a local directory containing shared deployment state. It is not itself one Kubernetes deployment. A workspace can contain multiple lake environments.

A lake environment is one Tanka entrypoint directory inside the workspace. It is identified by a marked `spec.json`. The environment path is whatever workspace-relative path the user passes to `lake add`, for example `dev` or `lakes/prod`.

A product is a named product specification stored inside a lake environment. The compact product is saved as `ENV/<productName>.json`. The fully resolved product is saved as `ENV/<productName>_fullspec.json`.

The active product is the product that `main.jsonnet`, `lake verify`, and `lake bootstrap` consume. It is stored directly in `ENV/spec.json` at `spec.stelar.active_product`. The active product name is stored at `spec.stelar.active_product_name`.

Bootstrap state is stored in `ENV/spec.json` at `spec.stelar.bootstrapped_product` after `lake bootstrap` succeeds. It records the bootstrapped product name, the bootstrap target hash, the bootstrap Secret names, and a timestamp.

## File Layout

`jsonnetfile.json` is the workspace Jsonnet Bundler dependency file. `stelarctl workspace init` creates or merges it. `jb install` consumes it and creates `vendor/`.

`lib/` is created by `workspace init` as a local workspace directory. The STELAR Jsonnet library used by generated environments is expected under `vendor/lib` after `jb install`.

`ENV/main.jsonnet` is copied by `lake add` from the vendored STELAR template. It imports `./spec.json` and passes `spec.stelar.active_product` to `build_lake`.

`ENV/spec.json` is the Tanka environment spec and the stelarctl state file. It contains the lake marker, optional context/namespace target fields, active product state, optional bootstrap state, and Tanka metadata/labels after bootstrap.

`ENV/manual_tls.yaml` is an optional operator-provided file used only when the active product selects manual TLS. It contains endpoint-to-directory mappings. Secret names come from the active fullspec, not from this YAML file.

## Normal Workflow

1. `stelarctl workspace init WORKSPACE` creates the workspace skeleton and `jsonnetfile.json`.

2. The user runs `jb install` from the workspace so `vendor/` is populated.

3. `stelarctl lake add ENV` creates a marked lake environment and copies `main.jsonnet`.

4. `stelarctl lake create PRODUCT ENV` or `stelarctl lake create --minimal PRODUCT_NAME ENV` creates named product files inside the environment.

5. The first created product is activated automatically. Later products are not activated automatically.

6. `stelarctl lake activate PRODUCT_NAME ENV` changes the active product.

7. `stelarctl lake verify ENV` runs read-only validation against the configured or supplied cluster target.

8. `stelarctl lake bootstrap ENV` completes missing target fields before first bootstrap, runs preflight checks unless skipped, creates bootstrap Secrets, and records bootstrap state.

9. The user runs `tk apply ENV` to create the Tanka-rendered Kubernetes resources.

10. `stelarctl lake status ENV` reports bootstrap Secret state and selected workload state.

11. Cleanup uses `tk delete ENV` for rendered resources and `stelarctl lake purge-secrets ENV` for bootstrap Secrets.

## Workspace Commands

`workspace init WORKSPACE [--force]` creates the workspace directory when missing, creates `lib/`, and writes the packaged `jsonnetfile.json` template.

If `jsonnetfile.json` already exists and `--force` is not used, missing required dependencies are merged into it when possible. Existing dependency pins are preserved. Invalid JSON or invalid dependency structure fails the command.

If `--force` is used, `jsonnetfile.json` is rewritten from the packaged template. This can discard local edits to that file.

`workspace info [WORKSPACE]` is read-only. It reports whether the workspace directory, `jsonnetfile.json`, `lib/`, `vendor/`, and marked lake environments exist. It does not require a fully initialized workspace, but the path must be a directory.

## Lake Environment Commands

`lake add ENV [--workspace WORKSPACE] [--context CONTEXT] [--namespace NAMESPACE] [--adopt-existing-main]` creates or adopts a lake environment.

`lake add` requires a valid workspace containing `jsonnetfile.json`. It expects the vendored environment template to exist, which normally means the user already ran `jb install`.

If `ENV` does not exist, `lake add` creates it, copies `main.jsonnet`, creates `spec.json`, and marks it as a stelarctl lake environment.

If `--context` or `--namespace` is supplied before bootstrap, those values are written into `spec.json`. Either flag may be omitted. Missing values can later be inferred by `lake bootstrap` before bootstrap state exists.

If `main.jsonnet` already exists but the directory is not marked as a lake environment, `lake add` fails by default. `--adopt-existing-main` takes over that directory only when `main.jsonnet` matches the managed stelarctl template, then creates or marks `spec.json`. Custom entrypoints are rejected.

If `spec.stelar.bootstrapped_product` already exists, `lake add` refuses to run. After bootstrap, context/namespace repair is manual `spec.json` repair only.

`lake list [--workspace WORKSPACE]` lists marked lake environments. Unmarked directories and invalid `spec.json` files are ignored.

`lake info ENV [--workspace WORKSPACE]` reports one marked environment: path, `main.jsonnet`, `spec.json`, active product presence, and generated product names.

`lake remove ENV [--workspace WORKSPACE] [--yes] [--force]` deletes a marked lake environment directory. It refuses unmarked directories. It prompts unless `--yes` is supplied. It refuses environments that still contain an active product or recorded bootstrap state unless `--force` is supplied. It deletes local files only, not Kubernetes resources.

## Product Creation And Activation

`lake create PRODUCT ENV [--workspace WORKSPACE]` loads an existing product JSON or YAML file, validates it against the feature model, resolves defaults into a fullspec, writes `ENV/<productName>.json`, writes `ENV/<productName>_fullspec.json`, and prints the fullspec.

In normal mode, `productName` comes from the product file stem. For example, `analytics.yaml` produces `analytics.json` and `analytics_fullspec.json`.

Normal `lake create` does not accept `--context` or `--namespace`. Those flags are target concerns, not product transformation concerns.

`lake create --minimal PRODUCT_NAME ENV [--workspace WORKSPACE] [--context CONTEXT] [--namespace NAMESPACE] [--manual-secrets] [--infer-storage-from-cluster]` interactively creates a minimal product.

Minimal creation supports only the minimal product shape. It does not create manual TLS products and does not select optional components.

Minimal creation defaults to generated secret values. `--manual-secrets` changes the prompts so the user supplies the secret values manually.

`--namespace` and `--context` in minimal mode write deployment target fields to `spec.json` when provided. `--context` is also used with `--infer-storage-from-cluster`, so storage class prompts can be inferred from that kube context. Product/fullspec files do not contain the Kubernetes namespace.

When the environment has no active product, the first successful product creation activates the generated fullspec automatically. Later product creations do not change the active product. If the regenerated product name is already active and the embedded active fullspec remains stale, the CLI warns. Before bootstrap, it tells the user to run `lake activate`; after bootstrap, it tells the user to purge old bootstrap Secrets, activate the regenerated product, and bootstrap again.

`lake activate PRODUCT_NAME ENV [--workspace WORKSPACE]` reads `ENV/<productName>.json` and `ENV/<productName>_fullspec.json`, validates the fullspec, writes it to `spec.stelar.active_product`, and writes `spec.stelar.active_product_name`.

Activation does not create Kubernetes Secrets and does not run Tanka.

If context and namespace exist in `spec.json`, activation tries to check whether current bootstrap Secrets already exist. Existing bootstrap Secrets produce a warning and activation proceeds. RBAC or kube context load failures also produce a warning and activation proceeds.

If activation selects the same fullspec whose bootstrap Secrets already exist, it prints informational output rather than a warning.

If recorded bootstrap state exists and the stored target hash no longer matches `spec.contextNames` and `spec.namespace`, activation is refused until `spec.json` is manually restored.

## Target Context And Namespace Rules

Before bootstrap state exists, context and namespace are flexible. `lake add` can write either value. `lake verify`, `lake status`, and `lake purge-secrets` can use `--context` and `--namespace` without writing them. `lake bootstrap` can infer missing values from kubeconfig and persist them.

`lake bootstrap` infers a missing context from the active kubectl context. It infers a missing namespace from the selected kube context namespace, falling back to `default` when kubeconfig has no namespace.

After bootstrap state exists, `spec.json` is authoritative. Commands must use the stored `spec.contextNames` and `spec.namespace`. `--context` and `--namespace` overrides are rejected by `lake verify`, `lake status`, and `lake purge-secrets`.

After bootstrap state exists, if either stored target field is missing, cluster-aware commands fail. The user must manually restore `spec.contextNames` and `spec.namespace`.

After bootstrap state exists, if the stored target fields do not hash to `spec.stelar.bootstrapped_product.target_sha256`, cluster-aware commands fail before acting on the cluster.

## Verification And Bootstrap

`lake verify ENV [--workspace WORKSPACE] [--context CONTEXT] [--namespace NAMESPACE]` is read-only. It validates the active fullspec, target availability, storage classes, ingress prerequisites, cert-manager prerequisites when needed, and manual TLS inputs when needed.

`lake verify` does not infer missing target fields and does not write `spec.json`. Before bootstrap, missing target fields may be supplied with flags. After bootstrap, target flags are rejected.

`lake bootstrap ENV [--workspace WORKSPACE] [--skip-preflight]` prepares an environment for `tk apply`.

`lake bootstrap` loads `spec.stelar.active_product`, resolves or validates the target context/namespace, updates Tanka metadata in `spec.json`, validates local config, loads the kube context, runs preflight checks unless skipped, checks existing bootstrap Secrets, creates required Secrets, applies manual TLS Secrets when selected, and records `spec.stelar.bootstrapped_product`.

The default preflight mode is strict. Strict preflight checks namespace existence, required StorageClasses, nginx ingress prerequisites, and cert-manager/ClusterIssuer readiness when cert-manager TLS is selected.

`--skip-preflight` bypasses only read-only prerequisite checks. It still loads kube context, validates local config, checks/creates Secrets, and records bootstrap state on success.

If all expected bootstrap Secrets already exist, bootstrap fails and reports that bootstrap appears to have already run.

If only some expected bootstrap Secrets exist, bootstrap fails because the namespace is partially bootstrapped. It does not create missing Secrets into a partial state.

If reading Secrets is forbidden by RBAC, bootstrap warns and proceeds at user risk. Kubernetes create conflicts still leave existing Secrets untouched.

If creating Secrets is forbidden or the Kubernetes API returns a non-conflict error, bootstrap fails.

## Secret Behavior

Product-derived Secrets are built from the active fullspec. The current product Secret categories include postgres/database passwords, Keycloak root password, API SMTP password, API session key, CKAN admin password, MinIO root password, and optional LLM search API key.

Manual TLS Secrets are included when the active fullspec selects `manual_tls`. Secret names come from `spec.stelar.active_product.ingress.manual_tls`. Certificate and key file directories come from `ENV/manual_tls.yaml`.

CKAN auth Secret behavior is currently inconsistent with the fullspec inventory. The feature model exposes `ckan.CKAN_AUTH_SECRET_NAME`, `ckan.CKAN_SESSION_KEY`, and `ckan.CKAN_JWT_KEY`, and manifests reference `config.ckan.CKAN_AUTH_SECRET_NAME`, but bootstrap still creates a hardcoded `ckan-auth-secret` with generated values. This is a known issue to fix before claiming CKAN auth is fully fullspec-driven.

## TLS Behavior

`SCHEME: http` requires `ingress.tls: [no_tls]` and `minio.INSECURE_MC_CLIENT: "true"`.

`SCHEME: https` rejects `no_tls`. The model and validator currently accept `cert_manager` and `manual_tls`.

`cert_manager` TLS expects `ingress.cert_manager.ClusterIssuer`. Preflight validates cert-manager CRDs, cert-manager deployments, and the configured ClusterIssuer. Jsonnet renders cert-manager Certificate resources for the known exposed domains.

`manual_tls` expects four Secret names in the active fullspec and a local `ENV/manual_tls.yaml` mapping endpoint names to directories containing `tls.crt` and `tls.key`. Bootstrap validates and applies those TLS Secrets.

The feature model currently lists both `nginx` and `traefik` ingress controllers. Rendering and preflight currently hardcode nginx. A product selecting `traefik` is valid in the model but will still render and verify against nginx. This is a known issue.

## Status Behavior

`lake status ENV [--workspace WORKSPACE] [--context CONTEXT] [--namespace NAMESPACE] [--wait --job-timeout SECONDS --poll-interval SECONDS]` is read-only.

Status requires an active product and a target context/namespace. Before bootstrap, missing target fields can be supplied with flags. After bootstrap, target flags are rejected.

Bootstrap status is inferred by checking expected Secret names. If bootstrap state exists, recorded Secret names are used. Otherwise, Secret names are derived from the active fullspec.

Bootstrap states are `bootstrapped`, `not_bootstrapped`, `partial`, and `unknown`.

`bootstrapped` means all expected bootstrap Secrets exist. `not_bootstrapped` means none exist. `partial` means only some exist. `unknown` means RBAC or an API error prevented inspection.

Deployment status is inferred from expected Deployments, StatefulSets, and init Jobs for selected components. Components with no implemented workload mapping are reported as unchecked.

Deployment states are `deployed`, `not_deployed`, `progressing`, `degraded`, `unknown`, and `unchecked`.

By default, status performs one snapshot check. `--job-timeout` and `--poll-interval` are valid only with `--wait`. `--wait` requires both values, and the CLI requires `--poll-interval` to be greater than 0. With `--wait`, init Jobs are polled until success or timeout.

## Cleanup Behavior

`tk delete ENV` is the cleanup mechanism for resources rendered by Tanka.

`lake purge-secrets ENV [--workspace WORKSPACE] [--context CONTEXT] [--namespace NAMESPACE] [--yes]` deletes only bootstrap Secrets. It does not delete Deployments, StatefulSets, Jobs, Services, Ingresses, PVCs, ConfigMaps, or any Tanka-rendered resource.

If bootstrap state exists, purge uses the recorded Secret names and requires the stored target to match the bootstrap hash. Target override flags are rejected after bootstrap.

If bootstrap state does not exist, purge derives expected Secret names from the active fullspec.

Purge prompts unless `--yes` is supplied. Missing Secrets are reported as already missing. RBAC delete failures fail the command.

`lake remove ENV` deletes the local environment directory only. It does not interact with Kubernetes, and it refuses active or bootstrapped environments unless `--force` is supplied so cleanup metadata is not lost accidentally.

## Rendering Behavior

`ENV/main.jsonnet` imports `./spec.json` and calls `build_lake(spec.stelar.active_product)`.

`build_lake` extracts selected components from `support`, `core_components`, `optional_components`, and `cluster`. It then renders components that exist in the static component registry.

The global config object passed to components is the unwrapped `klms` object from the active fullspec. Components read their config from this global object.

Component rendering is static-registry based. Jsonnet computed imports are not used. Adding a component requires adding a component entrypoint and registering it in `lib/util/components.libsonnet`.

## Current Known Issues

CKAN auth Secret creation is not fully fullspec-driven. Fix by deriving the Secret name and values from `config.ckan.CKAN_AUTH_SECRET_NAME`, `config.ckan.CKAN_SESSION_KEY`, and `config.ckan.CKAN_JWT_KEY`.


`traefik` ingress controller selection is model-valid but rendering/preflight are nginx-only. Either implement controller-specific behavior or remove/reject `traefik`.

Prometheus and Grafana are registered as placeholder components with skeleton manifests. Status reports them as unchecked because no native workload mapping exists yet.

Airflow is treated as a Helm-backed component and is currently reported as unchecked by status because native workload status mapping is not implemented yet.
