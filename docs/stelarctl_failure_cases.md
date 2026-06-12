# stelarctl Failure Cases

## `lake add`

- Fails when the workspace is invalid or `vendor/lib/environment_templates/main_template.jsonnet` is missing.
- Fails when `main.jsonnet` exists in an unmarked environment unless `--adopt-existing-main` is used.
- Fails adoption when the existing `main.jsonnet` does not match the managed template.

## `lake create`

- Fails when the environment is not initialized or the product file is invalid.
- Fails when feature-model validation fails.
- Fails when target flags are used outside `--minimal` mode.
- Fails when minimal-product prompts are aborted.

## `lake switch`

- Fails when the named product or fullspec file is missing.
- Fails when the selected fullspec is invalid.
- Warns, but proceeds, when the target namespace already has `stelar-lake-state` for another product.
- Warns, but proceeds, when cluster state cannot be inspected.

## `lake verify`

- Fails when context or namespace is missing and not provided by flags.
- Fails when kubeconfig cannot resolve the context.
- Fails when storage, ingress, cert-manager, ClusterIssuer, or manual TLS prerequisites are missing.
- Fails on RBAC errors for read-only preflight checks.

## `lake bootstrap`

- Fails when the active fullspec is missing or invalid.
- Fills missing context/namespace from kubeconfig before writing Tanka metadata.
- Fails when ConfigMap `stelar-lake-state` already exists in the target namespace.
- Fails when all or some expected bootstrap Secrets exist but `stelar-lake-state` is absent.
- Warns and attempts Secret creation when Secret reads are forbidden by RBAC.
- Fails on Secret creation conflicts or create/delete RBAC errors before recording ConfigMap state.
- Fails when manual TLS is selected but `ENV/manual_tls.yaml` or valid cert/key files are missing.

## `lake status`

- Fails when context or namespace is missing and not provided by flags.
- Fails when kubeconfig cannot resolve/load the context.
- Reports `not_bootstrapped` when `stelar-lake-state` is absent.
- Reports `partial` or `unknown` when ConfigMap exists but Secrets are missing or RBAC blocks inspection.

## `lake unbootstrap`

- Fails when context or namespace is missing and not provided by flags.
- Uses `stelar-lake-state` when present; otherwise falls back to the local active fullspec for failed-bootstrap cleanup.
- Fails on Secret or ConfigMap delete RBAC/API errors.
- Does not delete Tanka-rendered resources.
