# stelarctl Failure Cases

This document lists the expected failure cases for the current `stelarctl`
command surface. It is intended as an operator and implementation review aid.

## Common Failures

- Invalid command shape: missing required arguments, unknown commands, unknown flags, or invalid flag values.
- Invalid workspace for most `lake` commands: workspace path is not a directory or does not contain `jsonnetfile.json`.
- Invalid environment name: empty, absolute path, `.`, `..`, or otherwise invalid workspace-relative path.
- Uninitialized lake environment: missing environment directory, missing `main.jsonnet`, missing `spec.json`, or missing the stelarctl marker in `spec.json`.
- Invalid JSON/YAML files: unreadable files, invalid JSON in `spec.json`, empty product file, non-object product file, or invalid product schema.
- Filesystem failures: expected file is a directory, expected directory is a file, permission errors, read errors, or write errors.

## `workspace init`

- Fails if `WORKSPACE` exists as a file.
- Fails if `WORKSPACE/lib` exists but is not a directory.
- Fails if `jsonnetfile.json` exists as a directory.
- Fails if existing `jsonnetfile.json` is invalid JSON or has invalid dependency structure.
- Fails if the packaged `jsonnetfile.json` template is missing or invalid.
- Fails on filesystem write errors.
- With `--force`, it can overwrite `jsonnetfile.json`; without it, it merges missing dependencies.

## `workspace info`

- Fails if `WORKSPACE` is not a directory.
- Does not require a fully initialized workspace; it reports missing `jsonnetfile.json`, `lib/`, or `vendor/`.

## `lake add`

- Fails if `--context` or `--namespace` is provided as an empty value.
- Fails if `spec.stelar.bootstrapped_product` exists; restoration is a manual `spec.json` repair.
- Fails if workspace is invalid.
- Fails if `ENV` is an invalid environment path.
- Fails if the environment path exists as a file.
- Fails if `main.jsonnet` must be copied but the vendored template is missing; this usually means `jb install` was not run.
- Fails if `main.jsonnet` exists as a directory.
- Fails if `spec.json` exists as a directory.
- Fails if `spec.json` exists but is invalid JSON or has invalid `metadata` / `annotations`.
- Fails by default if `main.jsonnet` already exists but `spec.json` is missing or unmarked.
- `--adopt-existing-main` avoids only the implicit-adoption failure, and still fails unless the existing `main.jsonnet` matches the managed stelarctl template.

## `lake list`

- Fails if workspace is invalid.
- Otherwise mostly read-only; unmarked or invalid `spec.json` files are ignored as lake environments.

## `lake info`

- Fails if workspace is invalid.
- Fails if the environment is not initialized, is missing required files, or lacks the stelarctl marker.

## `lake remove`

- Fails if workspace or environment is invalid or unmarked.
- Fails if the user declines the confirmation prompt.
- Fails if the environment contains an active product or recorded bootstrap state and `--force` is not supplied.
- Fails on filesystem deletion errors.
- `--yes` skips the prompt only; it does not bypass the metadata safety guard.
- `--force` bypasses the metadata safety guard and can discard cleanup state.

## `lake create`

- Fails if minimal-only flags are used without `--minimal`: currently `--custom-secret-names` and `--infer-storage-from-cluster`.
- Fails if normal mode is missing `ENV`.
- Fails if normal mode product path does not exist.
- Fails if normal mode uses `--context` or `--namespace`; normal product transformation does not write target fields. Use `lake add --context/--namespace` or `lake create --minimal --context/--namespace` before bootstrap.
- Fails if product name is empty, contains path separators, or contains invalid characters.
- Fails if product file is unreadable, empty, not an object, or invalid against the product schema or feature model.
- Fails if fullspec validation fails, including scheme/TLS mismatch, missing manual TLS secret names, invalid MinIO/security constraints, or invalid MinIO/security constraints.
- In `--minimal` mode, fails if `ENV` is missing or not initialized.
- In `--minimal --infer-storage-from-cluster`, fails if kube context or StorageClass inference cannot run.
- In interactive minimal mode, invalid prompt values are rejected; user abort exits.

## `lake activate`

- Fails if workspace or environment is invalid.
- Fails if product name is invalid.
- Fails if `ENV/<productName>.json` is missing.
- Fails if `ENV/<productName>_fullspec.json` is missing.
- Fails if the fullspec is invalid, especially scheme/TLS consistency.
- Fails if `spec.json` cannot be updated.
- Does not fail when bootstrap Secrets already exist or cannot be checked; it warns and proceeds.
- Re-activating the same already bootstrapped product prints informational output instead of a warning.

## `lake manual-tls-template`

- Fails if output file exists and `--force` is not used.
- Fails if the output parent directory cannot be created.
- Fails if the packaged template is missing.
- Fails on write errors.

## `lake verify`

- Fails if workspace or environment is invalid.
- Fails if `spec.stelar.active_product` is missing.
- Fails if context is missing from both `spec.json` and `--context`.
- Fails if namespace is missing from both `spec.json` and `--namespace`.
- Fails if the requested kube context does not exist or cannot be loaded.
- Fails if `spec.stelar.bootstrapped_product` exists and `spec.contextNames` or `spec.namespace` is missing; flags cannot substitute for restoring `spec.json`.
- Fails if `spec.stelar.bootstrapped_product` exists and `--context` or `--namespace` is supplied; the stored `spec.json` target is authoritative after bootstrap.
- Fails if `spec.stelar.bootstrapped_product.target_sha256` does not match the stored context/namespace target.
- Fails on invalid fullspec config: missing storage classes in config, invalid scheme/TLS/MinIO/manual TLS config.
- Fails if preflight resources are absent: namespace, StorageClasses, nginx IngressClass/controller, cert-manager CRDs/deployments, or ClusterIssuer.
- Fails with a clear RBAC message if read-only preflight checks are forbidden.

## `lake bootstrap`

- Fails if workspace or environment is invalid.
- Fails if `spec.stelar.active_product` is missing or invalid.
- Fails if kube contexts cannot be listed, no active context exists, requested context does not exist, or context cannot be loaded.
- Fails if namespace cannot be inferred or configured namespace/preflight namespace is missing.
- Fails if `spec.stelar.bootstrapped_product` exists and `spec.contextNames` or `spec.namespace` is missing.
- Fails if `spec.stelar.bootstrapped_product.target_sha256` does not match the stored context/namespace target.
- Fails on fullspec consistency errors: invalid scheme, missing TLS mode, HTTP with TLS, HTTPS without TLS, invalid MinIO credentials, short passwords, or missing secret fields.
- Fails if strict preflight detects missing namespace, StorageClasses, ingress, cert-manager, or ClusterIssuer readiness.
- Fails if strict preflight is blocked by RBAC; user can rerun with `--skip-preflight`.
- Fails if all bootstrap Secrets already exist, because bootstrap already happened.
- Fails if only some bootstrap Secrets exist, because partial bootstrap state is unsafe.
- If Secret reads are RBAC-forbidden, it warns and proceeds at user risk.
- Fails if creating Secrets is forbidden or the Kubernetes API returns non-conflict errors.
- For manual TLS, fails if `manual_tls.yaml` is missing, invalid, points to missing files, contains invalid PEM, or required manual TLS names are missing.

## `lake status`

- Fails if workspace or environment is invalid.
- Fails if `spec.stelar.active_product` is missing.
- Fails if the active fullspec fails local scheme/TLS, MinIO, manual TLS, or password validation.
- Fails if context or namespace is missing and not supplied by flags.
- Fails if `spec.stelar.bootstrapped_product` exists and `spec.contextNames` or `spec.namespace` is missing; flags cannot substitute for restoring `spec.json`.
- Fails if `spec.stelar.bootstrapped_product` exists and `--context` or `--namespace` is supplied; the stored `spec.json` target is authoritative after bootstrap.
- Fails if `spec.stelar.bootstrapped_product.target_sha256` does not match the stored context/namespace target.
- Fails if `--job-timeout` or `--poll-interval` is used without `--wait`.
- Fails if `--wait` is used without both `--job-timeout` and `--poll-interval`.
- Fails if timeout values are negative or if the CLI poll interval is not greater than 0.
- Does not fail when workloads or Secrets are missing; it reports `not_bootstrapped`, `partial`, `missing`, `progressing`, `degraded`, or `unknown`.

## `lake purge-secrets`

- Fails if workspace or environment is invalid.
- Fails if both `spec.stelar.bootstrapped_product` and `spec.stelar.active_product` are missing.
- Fails if context or namespace is missing and not supplied by flags.
- Fails if `spec.stelar.bootstrapped_product` exists and `spec.contextNames` or `spec.namespace` is missing; flags cannot substitute for restoring `spec.json`.
- Fails if `spec.stelar.bootstrapped_product` exists and `--context` or `--namespace` is supplied; the stored `spec.json` target is authoritative after bootstrap.
- Fails if `spec.stelar.bootstrapped_product.target_sha256` does not match the stored context/namespace target.
- Fails if user declines confirmation.
- Fails if deleting a Secret is RBAC-forbidden.
- Fails on non-404 Kubernetes delete errors.
- Does not fail for missing Secrets; it reports them as already missing.
- `--yes` skips the confirmation prompt.
