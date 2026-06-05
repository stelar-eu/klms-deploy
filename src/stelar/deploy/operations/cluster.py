"""Business logic for `lake bootstrap`."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from kubernetes import client as kube_client

from . import kube_context as kube_context_helpers
from kubernetes.client.rest import ApiException

from .cluster_preflight import PreflightAccessError, run_preflight_checks
from .common import CommandError, product_spec, read_environment_json, validate_workspace
from .deployment_config import (
    cluster_issuer_name,
    configured_storage_class_names,
    deployment_config,
    deployment_scheme,
)
from .environment_spec import (
    environment_context_name_or_none,
    environment_namespace,
    environment_namespace_or_none,
    update_environment_spec_json,
)
from .fullspec_validation import validate_config_scheme_tls_consistency
from .kube_context import load_kube_context, resolve_kube_context, resolve_kube_namespace
from .kubernetes_secrets import apply_product_secrets, apply_tls_secret_if_missing
from .lake_environment import complete_lake_environment_dir, initialized_lake_environment_dir
from .manual_tls import (
    MANUAL_TLS_FILE_NAME,
    manual_tls_selected,
    read_manual_tls_secrets,
)
from .progress import ClusterProgress

# Expose kube_config for tests and integrations that monkeypatch this module.
kube_config = kube_context_helpers.kube_config

PreflightMode = Literal["strict", "skip"]
PREFLIGHT_MODES = ("strict", "skip")


def bootstrap_lake(
    environment: str,
    workspace_path: Path = Path("."),
    preflight: PreflightMode = "strict",
    progress: ClusterProgress | None = None,
) -> None:
    """Prepare cluster resources for an initialized lake environment."""
    preflight = _validate_preflight_mode(preflight)
    progress = progress or ClusterProgress()
    workspace = validate_workspace(workspace_path)
    environment_dir = complete_lake_environment_dir(workspace, environment)
    product_data = read_environment_json(environment_dir / "product.json")
    product_fullspec = read_environment_json(
        environment_dir / "product_fullspec.json"
    )
    spec = product_spec(product_data)
    spec_path = environment_dir / "spec.json"
    spec_json = read_environment_json(spec_path)

    configured_context = environment_context_name_or_none(spec_json)
    if configured_context is None:
        context_name = resolve_kube_context(None)
        _notify_progress(progress, "inferred_context", context_name)
    else:
        context_name = resolve_kube_context(configured_context)

    configured_namespace = environment_namespace_or_none(spec_json)
    if configured_namespace is None:
        namespace = resolve_kube_namespace(context_name)
        _notify_progress(progress, "inferred_namespace", namespace, context_name)
    else:
        namespace = configured_namespace

    environment_name = environment_dir.relative_to(workspace.path)
    update_environment_spec_json(
        spec_path,
        environment_name,
        product_data,
        context_name=context_name,
        namespace=namespace,
    )
    spec_json = read_environment_json(spec_path)
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


def check_lake_cluster(
    environment: str,
    workspace_path: Path = Path("."),
    *,
    context: str | None = None,
    namespace: str | None = None,
) -> None:
    """Run bootstrap preflight checks without mutating files or creating Secrets."""
    workspace = validate_workspace(workspace_path)
    environment_dir = initialized_lake_environment_dir(workspace, environment)
    spec_json = read_environment_json(environment_dir / "spec.json")
    product_fullspec_path = environment_dir / "product_fullspec.json"
    if not product_fullspec_path.is_file():
        raise CommandError(
            f"Lake environment {environment!r} is missing product_fullspec.json"
        )
    product_fullspec = read_environment_json(product_fullspec_path)

    context_name = _required_check_context(environment, spec_json, context)
    check_namespace = _required_check_namespace(environment, spec_json, namespace)

    config = deployment_config(product_fullspec)
    validate_config_scheme_tls_consistency(config)
    storage_class_names = configured_storage_class_names(config)
    scheme = deployment_scheme(config)
    cluster_issuer = cluster_issuer_name(config, scheme)

    _validate_manual_tls_inputs_if_selected(environment_dir, config)

    load_kube_context(context_name)
    run_preflight_checks(
        check_namespace,
        storage_class_names,
        cluster_issuer,
        kube_client_module=kube_client,
        api_exception_type=ApiException,
    )


# Backwards-compatible operation name while the public CLI moves to `lake bootstrap`.
def init_lake_cluster(
    environment: str,
    workspace_path: Path = Path("."),
    context: str | None = None,
    preflight: PreflightMode = "strict",
    progress: ClusterProgress | None = None,
) -> None:
    """Compatibility wrapper for older callers of the cluster operation."""
    if context is not None:
        _write_legacy_context_override(environment, workspace_path, context)
    bootstrap_lake(environment, workspace_path, preflight=preflight, progress=progress)


def _write_legacy_context_override(
    environment: str,
    workspace_path: Path,
    context: str,
) -> None:
    workspace = validate_workspace(workspace_path)
    environment_dir = complete_lake_environment_dir(workspace, environment)
    product_data = read_environment_json(environment_dir / "product.json")
    update_environment_spec_json(
        environment_dir / "spec.json",
        environment_dir.relative_to(workspace.path),
        product_data,
        context_name=context,
    )


def _required_check_context(
    environment: str,
    spec_json: dict[str, object],
    context: str | None,
) -> str:
    if context is not None:
        return resolve_kube_context(_required_flag_value(context, "context"))

    configured_context = environment_context_name_or_none(spec_json)
    if configured_context is None:
        raise CommandError(
            f"Lake environment {environment!r} has no context in spec.json. "
            "Rerun with --context CONTEXT, or record it with "
            "`stelarctl lake create ... --context CONTEXT`."
        )
    return resolve_kube_context(configured_context)


def _required_check_namespace(
    environment: str,
    spec_json: dict[str, object],
    namespace: str | None,
) -> str:
    if namespace is not None:
        return _required_flag_value(namespace, "namespace")

    configured_namespace = environment_namespace_or_none(spec_json)
    if configured_namespace is None:
        raise CommandError(
            f"Lake environment {environment!r} has no namespace in spec.json. "
            "Rerun with --namespace NAMESPACE, or record it with "
            "`stelarctl lake create ... --namespace NAMESPACE`."
        )
    return configured_namespace


def _required_flag_value(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CommandError(f"--{name} must be a non-empty value")
    return value.strip()


def _validate_manual_tls_inputs_if_selected(
    environment_dir: Path,
    config: dict[str, object],
) -> None:
    if not manual_tls_selected(config):
        return

    manual_tls_path = environment_dir / MANUAL_TLS_FILE_NAME
    if not manual_tls_path.exists():
        raise CommandError(
            f"product_fullspec.json selects manual_tls, but {manual_tls_path} "
            "does not exist. Generate a sample with `stelarctl lake "
            f"manual-tls-template {manual_tls_path}` and edit it before running "
            "lake verify."
        )
    read_manual_tls_secrets(manual_tls_path, config)


def _notify_progress(progress: ClusterProgress, method_name: str, *args: str) -> None:
    method = getattr(progress, method_name, None)
    if method is not None:
        method(*args)


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
            "does not exist. Generate a sample with `stelarctl lake "
            f"manual-tls-template {manual_tls_path}` and edit it before running "
            "lake bootstrap."
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
