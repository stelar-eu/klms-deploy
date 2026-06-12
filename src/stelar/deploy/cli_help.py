"""Centralized help text for the stelarctl CLI.

The CLI uses Typer/Rich, so keeping command descriptions here avoids scattering
operator-facing wording across command handlers. Keep this file focused on what
an operator needs to know at the terminal: workflow order, generated files, and
safety boundaries.
"""

from __future__ import annotations

import inspect
from textwrap import dedent

import typer

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


class LinePreservingEpilogGroup(typer.core.TyperGroup):
    """Typer group that renders epilog text without collapsing newlines."""

    def format_epilog(self, ctx, formatter) -> None:  # noqa: ANN001
        if not self.epilog:
            return
        formatter.write_paragraph()
        formatter.write(inspect.cleandoc(self.epilog) + "\n")


def show_help_on_no_args(ctx: typer.Context) -> None:
    """Print group help and exit successfully when no subcommand is selected."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()

ROOT_HELP = (
    "Prepare a STELAR KLMS lake deployment workspace before rendering or "
    "applying Kubernetes manifests with Tanka. stelarctl creates the workspace "
    "layout, resolves product specs into fullspecs, updates Tanka environment "
    "metadata, checks cluster prerequisites, and creates deployment secrets."
)
ROOT_EPILOG = dedent(
    """
    Command reference:
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
                   --custom-secret-names, --infer-storage-from-cluster
      stelarctl lake switch PRODUCT_NAME ENV
          options: --workspace WORKSPACE
      stelarctl lake manual-tls-template [OUTPUT]
          options: --force
      stelarctl lake verify ENV
          options: --workspace WORKSPACE, --context CONTEXT, --namespace NAMESPACE
      stelarctl lake status ENV
          options: --workspace WORKSPACE, --context CONTEXT, --namespace NAMESPACE,
                   --wait, --job-timeout SECONDS, --poll-interval SECONDS
      stelarctl lake unbootstrap ENV
          options: --workspace WORKSPACE, --context CONTEXT, --namespace NAMESPACE, --yes
      stelarctl lake bootstrap ENV
          options: --workspace WORKSPACE, --skip-preflight, --manual-secrets

    Typical workflow: run `workspace init`, then `jb install`, then
    `lake add`, then `lake create --minimal PRODUCT_NAME ENV` or `lake create PRODUCT ENV`.
    The first created product is selected automatically; run
    `lake switch PRODUCT_NAME ENV` only when switching products or after
    regenerating the active product. If manual TLS is selected, create
    `ENV/manual_tls.yaml` with `lake manual-tls-template`. Optionally run
    `lake verify`, then `lake bootstrap`, and finally `tk apply ENV`. Cleanup
    is explicit too: run `tk delete ENV` for rendered manifests, then
    `lake unbootstrap ENV` if bootstrap Secrets
    should also be removed.

    Main concepts: a workspace is the root with jsonnetfile.json, vendor/, and
    lake environments. An environment is one Tanka directory marked by spec.json
    at the path selected with `lake add`; a product is the user-selected
    feature/configuration input; a fullspec is the generated, fully defaulted
    config. The active fullspec in spec.json is consumed by Jsonnet; cluster status uses the stelar-lake-state ConfigMap written during bootstrap.

    Safety boundary: stelarctl scaffolds files and creates missing Kubernetes
    Secrets. It does not run tk apply for you. Read-only preflight checks can be
    skipped with --skip-preflight when RBAC prevents inspection. Cleanup is
    split deliberately: use tk delete ENV for rendered manifests and
    lake unbootstrap ENV for bootstrap Secrets created outside Tanka.
    """
).strip()

LAKE_MANUAL_TLS_TEMPLATE_HELP = (
    "Write the manual_tls.yaml input template used by lake bootstrap when a "
    "product selects ingress.tls manual_tls. The file maps each public endpoint "
    "to a directory containing tls.crt and tls.key."
)
LAKE_MANUAL_TLS_TEMPLATE_EPILOG = dedent(
    """
    Place the edited file at ENV/manual_tls.yaml before running
    lake bootstrap. The YAML contains certificate directories only; Kubernetes
    Secret names come from spec.stelar.active_product ingress.manual_tls.

    Expected endpoint keys are primary, keycloak, minio_api, and registry. Each
    referenced directory must contain a matching PEM certificate/key pair named
    tls.crt and tls.key.
    """
).strip()

LAKE_CREATE_HELP = (
    "Create product files inside a lake environment. Use PRODUCT ENV to resolve "
    "an existing product, or --minimal PRODUCT_NAME ENV to create a prompted minimal product."
)
LAKE_CREATE_EPILOG = dedent(
    """
    Modes: PRODUCT ENV validates an existing product JSON/YAML file.
    --minimal PRODUCT_NAME ENV prompts for a core-only lake product and writes
    it directly into ENV. PRODUCT_NAME may be given as name or name.json.

    Outputs: ENV/<productName>.json keeps the validated product input.
    ENV/<productName>_fullspec.json contains all feature-model defaults. Use
    --print-fullspec to also print the generated fullspec JSON to stdout.
    lake create selects the generated product only when the environment has no
    active product yet. Later creations do not change ENV/spec.json; use
    lake switch PRODUCT_NAME ENV to switch the deployable product.

    Minimal mode does not write password values into product files. Secret names
    use feature-model defaults unless --custom-secret-names is provided. Actual
    Secret values are generated later by lake bootstrap. In minimal mode,
    --namespace and --context write deployment target fields to ENV/spec.json;
    --context is also used by --infer-storage-from-cluster.

    Minimal mode supports only http/no_tls and https/cert_manager. It does not
    generate manual_tls products; use an existing product plus lake
    manual-tls-template when manually supplied certificates are needed.

    Validation highlights: http requires no_tls and minio.INSECURE_MC_CLIENT=true;
    https requires cert_manager or manual_tls; manual_tls requires
    PRIMARY_TLS_SECRET_NAME, KEYCLOAK_TLS_SECRET_NAME, MINIO_API_TLS_SECRET_NAME,
    and REGISTRY_TLS_SECRET_NAME.
    """
).strip()

LAKE_SWITCH_HELP = (
    "Set one generated product as the active deployable product for a lake "
    "environment."
)
LAKE_SWITCH_EPILOG = dedent(
    """
    PRODUCT_NAME may be given as name or name.json. The command reads
    ENV/<productName>.json and ENV/<productName>_fullspec.json, validates the
    fullspec, and writes it to ENV/spec.json at spec.stelar.active_product.
    The selected name is recorded at spec.stelar.current_product.

    Switching does not run preflight checks, create Kubernetes Secrets, or run
    tk apply. It only changes the local fullspec that main.jsonnet renders. If
    the target namespace already contains stelar-lake-state for a different
    product, the command warns; unbootstrap and rerun lake bootstrap before
    applying the switched product to that same namespace.
    """
).strip()


WORKSPACE_HELP = (
    "Create, inspect, and maintain STELAR deployment workspace roots. A "
    "workspace contains jsonnetfile.json, vendor/ after jb install, and "
    "workspace-relative lake environment directories."
)
WORKSPACE_EPILOG = dedent(
    """
    Use workspace init before running jb install. Use workspace info when you
    need to check whether dependencies, environments, and generated product files
    are present.
    """
).strip()

WORKSPACE_INIT_HELP = (
    "Create or update a deployment workspace root. The command creates "
    "the workspace directory, ensures local lib/ exists, and writes or "
    "merges jsonnetfile.json."
)
WORKSPACE_INIT_EPILOG = dedent(
    """
    After this command, run jb install from the workspace root. Jsonnet Bundler
    downloads the vendored STELAR deployment library and its Jsonnet dependencies
    into vendor/.

    Existing jsonnetfile.json files are merged with the required dependency when
    possible. Use --force only when you intentionally want to rewrite it from the
    packaged template.
    """
).strip()

WORKSPACE_INFO_HELP = (
    "Print read-only workspace state: jsonnetfile.json, lib/, vendor/, "
    "lake environments, and generated files inside each environment."
)
WORKSPACE_INFO_EPILOG = dedent(
    """
    WORKSPACE defaults to the current directory. The command does not run jb,
    Tanka, or kubectl; it only inspects local files.
    """
).strip()

LAKE_HELP = (
    "Manage lake environments inside an existing workspace. Use this group to "
    "add, list, inspect, remove, and prepare environments for Kubernetes."
)
LAKE_EPILOG = dedent(
    """
    Required order: workspace init, then jb install from the workspace root,
    then lake add, then lake create. The first created product is selected
    automatically; use lake switch only to switch products or refresh a
    regenerated active product. Use lake list and lake info to inspect local environments. Use lake status
    to inspect the target cluster. The final Kubernetes apply is explicit: run
    tk apply ENV after lake bootstrap succeeds. Cleanup is also explicit: run
    tk delete ENV for rendered resources and lake unbootstrap ENV for
    bootstrap Secrets created outside Tanka.
    """
).strip()

LAKE_ADD_HELP = (
    "Create one Tanka environment at ENV relative to the workspace. The "
    "spec.json marker identifies it as a stelarctl lake environment. The "
    "environment later receives "
    "named product artifacts, active product state in spec.json, "
    "and optional manual_tls.yaml."
)
LAKE_ADD_EPILOG = dedent(
    """
    This command expects jb install to have populated vendor/ because the Tanka
    main_template.jsonnet is copied from the vendored STELAR deployment library
    as the environment main.jsonnet entrypoint.
    Pass --context and/or --namespace to write the initial Kubernetes target into
    spec.json before the first successful bootstrap. Each flag is optional; omitted
    target fields can still be inferred later by lake bootstrap before the
    cluster-side stelar-lake-state ConfigMap is written.

    Existing marked environments are preserved for idempotent pre-bootstrap reruns. If
    main.jsonnet already exists but spec.json is missing or unmarked, the command
    stops to avoid silently taking over an arbitrary Tanka entrypoint.
    --adopt-existing-main means: keep the existing main.jsonnet only when
    it matches the managed stelarctl main_template.jsonnet, create or mark
    spec.json with the stelarctl lake marker, and treat the directory as managed
    by stelarctl from then on. Custom Tanka entrypoints are rejected.
    """
).strip()

LAKE_LIST_HELP = (
    "List stelarctl-marked lake environments in a workspace. The command scans "
    "spec.json markers and ignores ordinary unmarked Tanka directories."
)
LAKE_LIST_EPILOG = dedent(
    """
    Use this to see which workspace-relative paths stelarctl will accept for
    lake create, lake switch, lake info, lake remove, lake verify, lake status,
    lake unbootstrap, and lake bootstrap.
    """
).strip()

LAKE_INFO_HELP = (
    "Show file-level state for one stelarctl-marked lake environment."
)
LAKE_INFO_EPILOG = dedent(
    """
    The environment must already contain main.jsonnet and a marked spec.json.
    The command reports whether an active product is set and which generated
    named products are available.
    """
).strip()

LAKE_REMOVE_HELP = (
    "Delete one stelarctl-marked lake environment directory from the workspace."
)
LAKE_REMOVE_EPILOG = dedent(
    """
    Removal is intentionally limited to marked lake environments so arbitrary
    workspace directories are not deleted by typo. The command asks for
    confirmation unless --yes is supplied. It refuses to remove environments
    that still contain an active product unless --force is supplied. Use --force
    only after `tk delete ENV` and `stelarctl lake unbootstrap ENV`, or when
    you intentionally want to discard local metadata.
    """
).strip()


LAKE_VERIFY_HELP = (
    "Verify that a lake environment is ready for bootstrap/apply against a "
    "Kubernetes cluster. The command requires spec.stelar.active_product plus an "
    "explicit or spec.json context and namespace, and it never writes spec.json "
    "or creates Secrets."
)
LAKE_VERIFY_EPILOG = dedent(
    """
    Required inputs: the environment must be a stelarctl-marked lake environment,
    ENV/spec.json must define spec.stelar.active_product, and a Kubernetes context
    and namespace must be available either in ENV/spec.json or through
    --context/--namespace.

    Missing target fields are not inferred and not written. If context or
    namespace is missing from spec.json, rerun this command with --context
    and/or --namespace, or let lake bootstrap infer and persist them.

    Checks performed: fullspec scheme/TLS/MinIO consistency, storage class
    prerequisites, nginx ingress prerequisites, cert-manager/ClusterIssuer
    prerequisites when cert_manager TLS is selected, and manual TLS input
    validation when manual_tls is selected. No Kubernetes Secrets are created.
    """
).strip()

LAKE_STATUS_HELP = (
    "Inspect bootstrap Secret state and selected-component workload status for "
    "one lake environment. The command is read-only and never writes spec.json."
)
LAKE_STATUS_EPILOG = dedent(
    """
    Required inputs: the environment must have a Kubernetes context/namespace
    in spec.json or supplied with --context/--namespace. Missing target fields
    are not inferred or written. Local active_product is not used as status
    truth; status reads the cluster-side stelar-lake-state ConfigMap.

    Bootstrap state is cluster-side: if ConfigMap stelar-lake-state is absent
    from the target namespace, the lake is reported as not_bootstrapped. When
    the ConfigMap exists, status reads the fullspec stored in it and checks the
    corresponding bootstrap Secrets and workloads.

    Deployment state is inferred from the Deployments, StatefulSets, and init
    Jobs expected by the selected fullspec components. By default the
    command performs one snapshot check. Use --wait together with required
    --job-timeout and a positive --poll-interval value when init Jobs
    should be polled until they complete.
    """
).strip()

LAKE_UNBOOTSTRAP_HELP = (
    "Undo lake bootstrap for one environment by deleting bootstrap Secrets "
    "and the cluster state ConfigMap. Use tk delete ENV separately for rendered manifests."
)
LAKE_UNBOOTSTRAP_EPILOG = dedent(
    """
    Required inputs: the environment must have a Kubernetes context/namespace
    in spec.json or supplied with --context/--namespace. Missing target fields
    are not inferred or written.

    Scope: when ConfigMap stelar-lake-state exists, this command reads its
    fullspec, deletes the corresponding bootstrap Secrets, and then deletes the
    ConfigMap so the namespace is no longer considered bootstrapped. If the
    ConfigMap is absent, it falls back to spec.stelar.active_product only as a
    cleanup path for failed bootstraps that created Secrets before recording
    cluster state. It does not delete Deployments, StatefulSets, Jobs, Services,
    PVCs, Ingresses, or any other Tanka-rendered resource; run tk delete ENV for
    those.

    Safety: missing Secrets are reported as already missing. RBAC delete failures
    stop the command with the Secret name and namespace. The command asks for
    confirmation unless --yes is supplied.
    """
).strip()

LAKE_BOOTSTRAP_HELP = (
    "Prepare an initialized environment for Kubernetes. The command completes "
    "missing spec.json context/namespace from kubeconfig, validates cluster "
    "prerequisites, and creates required fullspec/manual-TLS Secrets from a clean bootstrap state."
)
LAKE_BOOTSTRAP_EPILOG = dedent(
    """
    Context/namespace behavior: lake bootstrap preserves whichever fields are
    already present in ENV/spec.json. If contextNames is missing, it records the active kubectl context.
    If namespace is missing, it records the namespace configured on that context,
    falling back to Kubernetes default namespace when kubeconfig has none.

    Preflight checks verify namespace, storage classes, nginx ingress, and, when
    cert_manager TLS is selected, cert-manager plus the configured ClusterIssuer.

    RBAC behavior: if the Kubernetes user cannot perform a read-only check, the
    command stops and explains the missing access. Rerun with --skip-preflight
    only when you accept that cluster readiness will be discovered later by tk apply.

    Bootstrap state: after successful Secret creation, lake bootstrap writes
    ConfigMap stelar-lake-state in the target namespace. That ConfigMap records
    the product name, product input when available, and deployed fullspec. Its
    presence is the bootstrap marker for lake status and future bootstrap runs.

    Secret behavior: by default, lake bootstrap generates password and session
    Secret values with OS-backed randomness. Use --manual-secrets only when you
    want to type those values yourself; password prompts enforce at least 8
    characters. Before creating anything, lake bootstrap checks for
    stelar-lake-state and the required bootstrap Secrets for the active fullspec.
    If the ConfigMap exists, the command stops because bootstrap has already run.
    If all required Secrets exist but the ConfigMap is missing, the command stops
    because the namespace has inconsistent bootstrap state. If only some required
    Secrets exist, the command stops because the namespace is partially
    bootstrapped. If Secret reads are blocked by RBAC, it warns and attempts
    Secret creation directly; Kubernetes conflicts stop the command before the
    ConfigMap is recorded. If spec.stelar.active_product selects manual_tls,
    ENV/manual_tls.yaml must exist and point to valid tls.crt/tls.key pairs.

    HTTP behavior: HTTP deployments skip cert-manager checks and require MinIO
    insecure client mode in the fullspec.
    """
).strip()
