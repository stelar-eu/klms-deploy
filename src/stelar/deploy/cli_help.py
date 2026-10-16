"""Centralized terminal help for the stelarctl CLI."""

from __future__ import annotations

import inspect
from importlib.metadata import PackageNotFoundError, version as package_version
from textwrap import dedent

import typer

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


class LinePreservingEpilogCommand(typer.core.TyperCommand):
    """Render command epilogs as deliberately formatted terminal text."""

    def format_epilog(self, ctx, formatter) -> None:  # noqa: ANN001
        if not self.epilog:
            return
        formatter.write_paragraph()
        formatter.write(inspect.cleandoc(self.epilog) + "\n")


class LinePreservingEpilogGroup(typer.core.TyperGroup):
    """Render group epilogs as deliberately formatted terminal text."""

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


def root_callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        is_eager=True,
        help="Show the installed stelarctl version and exit",
    ),
) -> None:
    """Handle root options and show help when no command is supplied."""
    if version:
        try:
            installed_version = package_version("stelar-deploy")
        except PackageNotFoundError:
            installed_version = "unknown"
        typer.echo(f"stelarctl {installed_version}")
        raise typer.Exit()
    show_help_on_no_args(ctx)


ROOT_HELP = (
    "Prepare and operate STELAR KLMS lake deployments on Kubernetes. "
    "stelarctl manages local deployment configuration, validates cluster "
    "prerequisites, and creates bootstrap resources used by Tanka manifests."
)
ROOT_EPILOG = dedent(
    """
    Quick start:
      stelarctl workspace init ./klms-deploy
      cd ./klms-deploy
      jb install
      stelarctl lake add dev --context CONTEXT --namespace stelar-dev
      stelarctl lake create --minimal minimal dev
      stelarctl lake verify dev
      stelarctl lake bootstrap dev
      tk apply dev

    Inspect and clean up:
      stelarctl lake status dev --wait --job-timeout 600 --poll-interval 5
      tk delete dev
      stelarctl lake unbootstrap dev

    Concepts:
      workspace    Root containing jsonnetfile.json, vendor/, and environments.
      environment  Tanka directory managed by stelarctl, such as dev or prod.
      product      User-selected feature and configuration input.
      fullspec     Generated product configuration with all defaults resolved.

    Deployment boundary:
      stelarctl prepares files and bootstrap resources. It never runs tk apply
      or tk delete. Applying and deleting rendered workloads remains explicit.

    Run "stelarctl COMMAND --help" for command-specific options and examples.
    """
).strip()


WORKSPACE_HELP = (
    "Manage STELAR deployment workspaces. A workspace contains the Jsonnet "
    "dependency manifest, local overrides, vendored libraries, and lake "
    "environment directories."
)
WORKSPACE_EPILOG = dedent(
    """
    Typical workflow:
      stelarctl workspace init ./klms-deploy
      cd ./klms-deploy
      jb install
      stelarctl workspace info

    Run "stelarctl workspace COMMAND --help" for command-specific details.
    """
).strip()

WORKSPACE_INIT_HELP = (
    "Initialize a workspace directory and its Jsonnet dependency manifest. "
    "Existing compatible manifests are updated without discarding unrelated "
    "dependencies."
)
WORKSPACE_INIT_EPILOG = dedent(
    """
    Examples:
      stelarctl workspace init ./klms-deploy
      stelarctl workspace init . --force

    Creates or updates:
      WORKSPACE/jsonnetfile.json  Required Jsonnet dependencies.
      WORKSPACE/lib/              Local Jsonnet overrides.

    Existing jsonnetfile.json files are merged by default. --force rewrites the
    file from the packaged template and should be used only intentionally.

    Next step:
      cd WORKSPACE && jb install
    """
).strip()

WORKSPACE_INFO_HELP = (
    "Inspect local workspace state without running Jsonnet, Tanka, or kubectl."
)
WORKSPACE_INFO_EPILOG = dedent(
    """
    Examples:
      stelarctl workspace info
      stelarctl workspace info ./klms-deploy

    Reports:
      - workspace initialization and dependency files
      - vendor/ availability
      - managed lake environments
      - active and generated products per environment

    WORKSPACE defaults to the current directory. This command is read-only.
    """
).strip()


LAKE_HELP = (
    "Manage lake environments, product configuration, cluster validation, "
    "bootstrap resources, and deployment status."
)
LAKE_EPILOG = dedent(
    """
    Deployment lifecycle:
      stelarctl lake add ENV
      stelarctl lake create --minimal PRODUCT_NAME ENV
      stelarctl lake verify ENV
      stelarctl lake bootstrap ENV
      tk apply ENV
      stelarctl lake status ENV

    Cleanup lifecycle:
      tk delete ENV
      stelarctl lake unbootstrap ENV
      stelarctl lake remove ENV

    The first product created in an environment becomes active automatically.
    Use lake switch when selecting another product or refreshing a regenerated
    active product.

    Run "stelarctl lake COMMAND --help" for command-specific details.
    """
).strip()

LAKE_ADD_HELP = (
    "Create a managed Tanka environment inside a workspace and optionally "
    "record its kubectl context and Kubernetes namespace."
)
LAKE_ADD_EPILOG = dedent(
    """
    Examples:
      stelarctl lake add dev
      stelarctl lake add prod --context okeanos --namespace stelar-prod
      stelarctl lake add dev --adopt-existing-main

    Creates:
      ENV/main.jsonnet  Managed Tanka entrypoint copied from vendor/.
      ENV/spec.json     Environment marker, target, and active product state.

    Requirements:
      Run jb install first so vendor/lib/environment_templates is available.

    Target behavior:
      --context and --namespace are optional. If omitted, lake bootstrap can
      infer and persist missing values from kubeconfig.

    Safety:
      Existing managed environments are preserved. --adopt-existing-main only
      accepts an entrypoint identical to the stelarctl template; custom Tanka
      entrypoints are never silently replaced.
    """
).strip()

LAKE_LIST_HELP = "List all stelarctl-managed lake environments in a workspace."
LAKE_LIST_EPILOG = dedent(
    """
    Examples:
      stelarctl lake list
      stelarctl lake list --workspace ./klms-deploy

    The command scans spec.json markers and ignores ordinary, unmanaged Tanka
    directories. It is read-only.
    """
).strip()

LAKE_INFO_HELP = (
    "Show local files, active product state, and generated products for one "
    "managed lake environment."
)
LAKE_INFO_EPILOG = dedent(
    """
    Examples:
      stelarctl lake info dev
      stelarctl lake info lakes/prod --workspace ./klms-deploy

    The environment must contain main.jsonnet and a stelarctl-marked spec.json.
    This command inspects local files only; use lake status for cluster state.
    """
).strip()

LAKE_CREATE_HELP = (
    "Generate validated product and fullspec files in a lake environment. Use "
    "an existing JSON/YAML product or create an interactive minimal product."
)
LAKE_CREATE_EPILOG = dedent(
    """
    Examples:
      stelarctl lake create ./product.yaml dev
      stelarctl lake create --minimal minimal dev
      stelarctl lake create --minimal minimal dev --infer-storage-from-cluster
      stelarctl lake create --minimal minimal dev --context okeanos
      stelarctl lake create ./product.yaml dev --print-fullspec

    Modes:
      PRODUCT ENV
          Validate an existing JSON/YAML product and resolve feature defaults.
      --minimal PRODUCT_NAME ENV
          Prompt for a core-only product and write it directly into ENV.

    Outputs:
      ENV/<product>.json           Validated product input.
      ENV/<product>_fullspec.json  Fully resolved deployment configuration.

    Product selection:
      The first created product becomes active. Later products do not replace
      spec.stelar.active_product; use lake switch PRODUCT_NAME ENV.

    Secrets and TLS:
      Minimal products contain Secret names, never password values. lake
      bootstrap creates the values later. Minimal mode supports http/no_tls and
      https/cert_manager; it does not generate manual_tls products. HTTP requires
      minio.INSECURE_MC_CLIENT=true. Existing manual_tls products must define
      PRIMARY_TLS_SECRET_NAME, KEYCLOAK_TLS_SECRET_NAME,
      MINIO_API_TLS_SECRET_NAME, and REGISTRY_TLS_SECRET_NAME.
    """
).strip()

LAKE_SWITCH_HELP = "Select a generated product as the environment's active product."
LAKE_SWITCH_EPILOG = dedent(
    """
    Examples:
      stelarctl lake switch minimal dev
      stelarctl lake switch production.json prod --workspace ./klms-deploy

    Behavior:
      Reads ENV/<product>.json and ENV/<product>_fullspec.json, validates the
      fullspec, and updates spec.stelar.current_product and
      spec.stelar.active_product in ENV/spec.json.

    Safety:
      Switching changes local render input only. It does not run preflight,
      create Secrets, or run tk apply. If the namespace is already bootstrapped
      for another product, unbootstrap it before applying the switched product.
    """
).strip()

LAKE_MANUAL_TLS_TEMPLATE_HELP = (
    "Write a manual_tls.yaml template that maps public endpoints to local "
    "certificate directories."
)
LAKE_MANUAL_TLS_TEMPLATE_EPILOG = dedent(
    """
    Examples:
      stelarctl lake manual-tls-template dev/manual_tls.yaml
      stelarctl lake manual-tls-template dev/manual_tls.yaml --force

    Required location:
      Place the completed file at ENV/manual_tls.yaml before lake bootstrap.

    Required endpoint keys:
      primary, keycloak, minio_api, registry

    Each value must reference a directory containing tls.crt and tls.key. The
    Kubernetes Secret names are read from
    spec.stelar.active_product.ingress.manual_tls.
    """
).strip()

LAKE_VERIFY_HELP = (
    "Run read-only product and Kubernetes prerequisite checks before bootstrap "
    "or apply. The command never writes spec.json or creates Secrets."
)
LAKE_VERIFY_EPILOG = dedent(
    """
    Examples:
      stelarctl lake verify dev
      stelarctl lake verify dev --context okeanos --namespace stelar-dev

    Required state:
      - a managed environment with spec.stelar.active_product
      - a context and namespace in spec.json or supplied as command options

    Checks:
      - fullspec scheme, TLS, and MinIO consistency
      - namespace and configured StorageClasses
      - nginx IngressClass and controller
      - cert-manager and ClusterIssuer for cert_manager TLS
      - ENV/manual_tls.yaml inputs for manual_tls

    Overrides supplied with --context or --namespace are temporary. Missing
    target fields are not inferred or written. No Kubernetes Secrets are created.
    """
).strip()

LAKE_BOOTSTRAP_HELP = (
    "Prepare a lake environment for deployment by resolving its target, "
    "validating prerequisites, and creating bootstrap Secrets and state."
)
LAKE_BOOTSTRAP_EPILOG = dedent(
    """
    Examples:
      stelarctl lake bootstrap dev
      stelarctl lake bootstrap dev --manual-secrets
      stelarctl lake bootstrap dev --skip-preflight

    Target resolution:
      Existing context and namespace values in ENV/spec.json are preserved.
      Missing values are inferred from the active kubeconfig context and then
      persisted. A missing kubeconfig namespace defaults to "default".

    Preflight:
      Checks the namespace, StorageClasses, nginx ingress, and cert-manager plus
      the configured ClusterIssuer when cert_manager TLS is selected.
      --skip-preflight bypasses these read-only checks; use it only when RBAC
      prevents inspection and you accept later failure during tk apply.

    Bootstrap state:
      Creates required product and manual_tls Secrets, then writes the
      stelar-lake-state ConfigMap. Secret values are generated with OS-backed
      randomness unless --manual-secrets is used. Existing, partial, or
      inconsistent bootstrap state causes the command to stop without overwrite.

    This command does not apply rendered workloads. Run tk apply ENV after it
    succeeds. HTTP products skip cert-manager checks and require MinIO insecure
    client mode in the fullspec.
    """
).strip()

LAKE_STATUS_HELP = (
    "Inspect cluster-side bootstrap state and workload readiness for the "
    "components selected by a lake environment."
)
LAKE_STATUS_EPILOG = dedent(
    """
    Examples:
      stelarctl lake status dev
      stelarctl lake status dev --context okeanos --namespace stelar-dev
      stelarctl lake status dev --wait --job-timeout 600 --poll-interval 5

    Source of truth:
      Reads the stelar-lake-state ConfigMap from the target namespace. The local
      active product is not substituted when cluster state is absent.

    Reports:
      - bootstrapped, not_bootstrapped, partial, or unknown Secret state
      - readiness of expected Deployments, StatefulSets, and init Jobs
      - missing or unchecked components and access diagnostics

    The default is a single read-only snapshot. --wait polls init Jobs until
    success or --job-timeout; it requires a positive --poll-interval. Context
    and namespace overrides are temporary and never write spec.json.
    """
).strip()

LAKE_UNBOOTSTRAP_HELP = (
    "Remove bootstrap and init-generated resources for one lake environment. "
    "Rendered workloads must be deleted separately with Tanka."
)
LAKE_UNBOOTSTRAP_EPILOG = dedent(
    """
    Examples:
      stelarctl lake unbootstrap dev
      stelarctl lake unbootstrap dev --yes
      stelarctl lake unbootstrap dev --context okeanos --namespace stelar-dev

    Cleanup scope:
      Uses the fullspec in stelar-lake-state, or the local active product for a
      partial deployment without cluster state. It deletes bootstrap Secrets by
      exact name, plus init-generated Secret/ConfigMap names including Keycloak
      client/admin Secrets, ckan-admin-token-secret, Quay registry-config, and
      stelar-lake-state. Unrelated namespace resources are preserved.

    Safety:
      This is destructive. Every selected resource is printed before the prompt.
      --yes skips the prompt but not the warning. UID and resourceVersion
      preconditions protect resources replaced during cleanup. The command does
      not delete Deployments, StatefulSets, Jobs, Services, PVCs, or Ingresses.

    Recommended order:
      tk delete ENV
      stelarctl lake unbootstrap ENV
    """
).strip()

LAKE_REMOVE_HELP = "Delete a managed lake environment directory from the workspace."
LAKE_REMOVE_EPILOG = dedent(
    """
    Examples:
      stelarctl lake remove dev
      stelarctl lake remove dev --yes
      stelarctl lake remove dev --force --yes

    Safety:
      Only stelarctl-marked environment directories can be removed. Confirmation
      is required unless --yes is supplied. An active product blocks removal
      unless --force is used.

    Recommended order for a deployed environment:
      tk delete ENV
      stelarctl lake unbootstrap ENV
      stelarctl lake remove ENV
    """
).strip()
