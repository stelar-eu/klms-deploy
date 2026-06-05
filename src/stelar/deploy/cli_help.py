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
      stelarctl lake manual-tls-template [OUTPUT]
          options: --force
      stelarctl lake verify ENV
          options: --workspace WORKSPACE, --context CONTEXT, --namespace NAMESPACE
      stelarctl lake bootstrap ENV
          options: --workspace WORKSPACE, --skip-preflight

    Typical workflow: run `workspace init`, then `jb install`, then
    `lake add`, then `lake create --minimal` or `lake create PRODUCT ENV`,
    then `lake manual-tls-template` if manual TLS is selected, optionally
    `lake verify`, then `lake bootstrap`, and
    finally `tk apply ENV`.

    Main concepts: a workspace is the root with jsonnetfile.json, vendor/, and
    lake environments. An environment is one Tanka directory marked by spec.json
    at the path selected with `lake add`; a product is the user-selected
    feature/configuration input; a fullspec is the
    generated, fully defaulted config consumed by Jsonnet.

    Safety boundary: stelarctl scaffolds files and creates missing Kubernetes
    Secrets. It does not run tk apply for you. Read-only preflight checks can be
    skipped with --skip-preflight when RBAC prevents inspection.
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
    Secret names come from product_fullspec.json ingress.manual_tls.

    Expected endpoint keys are primary, keycloak, minio_api, and registry. Each
    referenced directory must contain a matching PEM certificate/key pair named
    tls.crt and tls.key.
    """
).strip()

LAKE_CREATE_HELP = (
    "Create product files inside a lake environment. Use PRODUCT ENV to resolve "
    "an existing product, or --minimal ENV to create a prompted minimal product."
)
LAKE_CREATE_EPILOG = dedent(
    """
    Modes: PRODUCT ENV validates an existing product JSON/YAML file.
    --minimal ENV prompts for a core-only lake product and writes it directly
    into ENV.

    Outputs: ENV/product.json keeps the validated product input;
    ENV/product_fullspec.json contains all feature-model defaults
    and is the config inventory consumed by Jsonnet. If --context or
    --namespace is supplied, lake create writes that field into ENV/spec.json.
    Missing spec context/namespace fields are filled later by lake bootstrap
    from kubeconfig. Minimal mode generates random secret values by default;
    use --manual-secrets only when you want to type those values yourself.

    Minimal mode supports only http/no_tls and https/cert_manager. It does not
    generate manual_tls products; use an existing product plus lake
    manual-tls-template when manually supplied certificates are needed.

    Validation highlights: http requires no_tls and minio.INSECURE_MC_CLIENT=true;
    https requires cert_manager, manual_tls, or self_signed; manual_tls requires
    PRIMARY_TLS_SECRET_NAME, KEYCLOAK_TLS_SECRET_NAME, MINIO_API_TLS_SECRET_NAME,
    and REGISTRY_TLS_SECRET_NAME.
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
    "Create or update a deployment workspace root. The command writes or merges "
    "jsonnetfile.json and creates the local lib/ directory."
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

INIT_LAKE_HELP = (
    "Manage lake environments inside an existing workspace. Use this group to "
    "add, list, inspect, remove, and prepare environments for Kubernetes."
)
INIT_LAKE_EPILOG = dedent(
    """
    Required order: workspace init, then jb install from the workspace root,
    then lake add, then lake create, then lake verify or lake bootstrap.
    Use lake list and lake info to inspect environments. Use lake remove to
    delete one. The final Kubernetes apply is explicit: run tk apply ENV after
    lake bootstrap succeeds.
    """
).strip()

INIT_LAKE_ENVIRONMENT_HELP = (
    "Create one Tanka environment at ENV relative to the workspace. The "
    "spec.json marker identifies it as a stelarctl lake environment. The "
    "environment later receives "
    "product.json, product_fullspec.json, "
    "spec.json metadata, and optional manual_tls.yaml."
)
INIT_LAKE_ENVIRONMENT_EPILOG = dedent(
    """
    This command expects jb install to have populated vendor/ because the Tanka
    main_template.jsonnet is copied from the vendored STELAR deployment library
    as the environment main.jsonnet entrypoint.
    Existing marked environments are preserved for idempotent reruns. If
    main.jsonnet already exists but spec.json is missing or unmarked, the command
    stops to avoid silently adopting an arbitrary Tanka entrypoint. Use
    --adopt-existing-main only when that directory should be managed by
    stelarctl.
    """
).strip()

LAKE_LIST_HELP = (
    "List stelarctl-marked lake environments in a workspace. The command scans "
    "spec.json markers and ignores ordinary unmarked Tanka directories."
)
LAKE_LIST_EPILOG = dedent(
    """
    Use this to see which workspace-relative paths stelarctl will accept for
    lake create, lake info, lake remove, lake verify, and lake bootstrap.
    """
).strip()

LAKE_INFO_HELP = (
    "Show file-level state for one stelarctl-marked lake environment."
)
LAKE_INFO_EPILOG = dedent(
    """
    The environment must already contain main.jsonnet and a marked spec.json.
    The command reports whether product.json and product_fullspec.json have been
    generated.
    """
).strip()

LAKE_REMOVE_HELP = (
    "Delete one stelarctl-marked lake environment directory from the workspace."
)
LAKE_REMOVE_EPILOG = dedent(
    """
    Removal is intentionally limited to marked lake environments so arbitrary
    workspace directories are not deleted by typo. The command asks for
    confirmation unless --yes is supplied.
    """
).strip()


LAKE_VERIFY_HELP = (
    "Verify that a lake environment is ready for bootstrap/apply against a "
    "Kubernetes cluster. The command requires product_fullspec.json plus an "
    "explicit or spec.json context and namespace, and it never writes spec.json "
    "or creates Secrets."
)
LAKE_VERIFY_EPILOG = dedent(
    """
    Required inputs: the environment must be a stelarctl-marked lake environment,
    ENV/product_fullspec.json must exist, and a Kubernetes context and namespace
    must be available either in ENV/spec.json or through --context/--namespace.

    Missing target fields are not inferred and not written. If context or
    namespace is missing from spec.json, rerun this command with --context
    and/or --namespace, or persist them with lake create.

    Checks performed: fullspec scheme/TLS/MinIO consistency, storage class
    prerequisites, nginx ingress prerequisites, cert-manager/ClusterIssuer
    prerequisites when cert_manager TLS is selected, and manual TLS input
    validation when manual_tls is selected. No Kubernetes Secrets are created.
    """
).strip()

LAKE_BOOTSTRAP_HELP = (
    "Prepare an initialized environment for Kubernetes. The command completes "
    "missing spec.json context/namespace from kubeconfig, validates cluster "
    "prerequisites, and creates missing product/manual-TLS Secrets."
)
LAKE_BOOTSTRAP_EPILOG = dedent(
    """
    Context/namespace behavior: lake create may write --context and --namespace
    into ENV/spec.json. lake bootstrap preserves whichever fields are already
    present. If contextNames is missing, it records the active kubectl context.
    If namespace is missing, it records the namespace configured on that context,
    falling back to Kubernetes default namespace when kubeconfig has none.

    Preflight checks verify namespace, storage classes, nginx ingress, and, when
    cert_manager TLS is selected, cert-manager plus the configured ClusterIssuer.

    RBAC behavior: if the Kubernetes user cannot perform a read-only check, the
    command stops and explains the missing access. Rerun with --skip-preflight
    only when you accept that cluster readiness will be discovered later by tk apply.

    Secret behavior: missing product secrets are created and existing secrets are
    left untouched. If product_fullspec.json selects manual_tls,
    ENV/manual_tls.yaml must exist and point to valid tls.crt/tls.key
    pairs.

    HTTP behavior: HTTP deployments skip cert-manager checks and require MinIO
    insecure client mode in the fullspec.
    """
).strip()
