"""Business logic for `init-lake cluster`."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from kubernetes import client as kube_client
from kubernetes import config as kube_config
from kubernetes.client.rest import ApiException

from .cluster_preflight import PreflightAccessError, run_preflight_checks
from .common import CommandError, product_spec, read_environment_json, validate_workspace
from .deployment_config import (
    cluster_issuer_name,
    configured_storage_class_names,
    deployment_config,
    deployment_scheme,
)
from .environment_spec import environment_namespace, update_environment_spec_json
from .fullspec_validation import validate_config_scheme_tls_consistency
from .kube_context import load_kube_context, resolve_kube_context
from .kubernetes_secrets import apply_product_secrets, apply_tls_secret_if_missing
from .lake_environment import complete_lake_environment_dir
from .manual_tls import (
    MANUAL_TLS_FILE_NAME,
    manual_tls_selected,
    read_manual_tls_secrets,
)
from .progress import ClusterProgress

PreflightMode = Literal["strict", "skip"]
PREFLIGHT_MODES = ("strict", "skip")


def init_lake_cluster(
    environment: str,
    workspace_path: Path = Path("."),
    context: str | None = None,
    preflight: PreflightMode = "strict",
    progress: ClusterProgress | None = None,
) -> None:
    """Initialize cluster resources for an initialized lake environment."""
    preflight = _validate_preflight_mode(preflight)
    progress = progress or ClusterProgress()
    workspace = validate_workspace(workspace_path)
    environment_dir = complete_lake_environment_dir(workspace, environment)
    product_data = read_environment_json(environment_dir / "product.json")
    product_fullspec = read_environment_json(
        environment_dir / "product_fullspec.json"
    )
    spec = product_spec(product_data)

    # Resolve the context before touching spec.json so an omitted --context is
    # recorded as the concrete active kubectl context Tanka will later use.
    context_name = resolve_kube_context(context)
    environment_name = environment_dir.relative_to(workspace.path)
    update_environment_spec_json(
        environment_dir / "spec.json",
        environment_name,
        context_name,
        product_data,
    )
    spec_json = read_environment_json(environment_dir / "spec.json")
    namespace = environment_namespace(spec_json)
    # Cluster-facing checks use the fullspec, not the original product, because
    # feature-model defaults are applied only in product_fullspec.json.
    config = deployment_config(product_fullspec)
    validate_config_scheme_tls_consistency(config)
    storage_class_names = configured_storage_class_names(config)
    scheme = deployment_scheme(config)
    cluster_issuer = cluster_issuer_name(config, scheme)

    load_kube_context(context_name)
    # --skip-preflight bypasses read-only cluster inspection only. Secret
    # creation still runs because the deployment cannot proceed without it.
    if preflight == "strict":
        run_preflight_checks(
            namespace,
            storage_class_names,
            cluster_issuer,
            kube_client_module=kube_client,
            api_exception_type=ApiException,
        )

    apply_product_secrets(namespace, spec, progress)
    _apply_manual_tls_secrets_if_present(environment_dir, namespace, config, progress)


def _validate_preflight_mode(preflight: str) -> PreflightMode:
    if preflight not in PREFLIGHT_MODES:
        raise CommandError("Preflight mode must be one of: strict, skip")
    return preflight  # type: ignore[return-value]


def _apply_manual_tls_secrets_if_present(
    environment_dir: Path,
    namespace: str,
    config: dict[str, object],
    progress: ClusterProgress,
) -> None:
    if not manual_tls_selected(config):
        return

    manual_tls_path = environment_dir / MANUAL_TLS_FILE_NAME
    if not manual_tls_path.exists():
        raise CommandError(
            f"product_fullspec.json selects manual_tls, but {manual_tls_path} "
            "does not exist. Generate a sample with `stelarctl product "
            f"init-manual-tls {manual_tls_path}` and edit it before running "
            "init-lake cluster."
        )

    # The fullspec owns the Kubernetes Secret names; manual_tls.yaml owns only
    # local certificate/key paths so operators can rotate files without editing
    # generated configuration.
    tls_secrets = read_manual_tls_secrets(manual_tls_path, config)
    core_api = kube_client.CoreV1Api()
    for tls_secret in tls_secrets:
        apply_tls_secret_if_missing(
            core_api,
            namespace,
            tls_secret.name,
            tls_secret.certificate,
            tls_secret.private_key,
            progress,
        )
