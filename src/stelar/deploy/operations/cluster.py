"""Business logic for `lake bootstrap`."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from kubernetes import client as kube_client

from . import kube_context as kube_context_helpers
from kubernetes.client.rest import ApiException

from .bootstrap_state import (
    bootstrap_secret_names,
    bootstrapped_product_or_none,
    record_bootstrapped_product,
    validate_bootstrap_product_matches,
    validate_bootstrap_target_matches,
)
from .cluster_preflight import PreflightAccessError, run_preflight_checks
from .common import CommandError, read_environment_json, validate_workspace
from .deployment_config import (
    cluster_issuer_name,
    configured_storage_class_names,
    deployment_config,
    deployment_scheme,
)
from .environment_spec import (
    environment_active_product,
    environment_active_product_name_or_none,
    environment_namespace,
    update_environment_spec_json,
)
from .environment_target import EnvironmentTarget, resolve_environment_target
from .fullspec_validation import validate_config_scheme_tls_consistency
from .kube_context import load_kube_context
from .kubernetes_secrets import (
    SecretReadForbidden,
    apply_product_secrets,
    apply_tls_secret_if_missing,
    check_secret_existence,
)
from .lake_environment import initialized_lake_environment_dir
from .manual_tls import (
    MANUAL_TLS_FILE_NAME,
    ManualTlsSecret,
    manual_tls_selected,
    read_manual_tls_secrets,
)
from .progress import ClusterProgress
from .secret_resources import expected_bootstrap_secret_names

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
    environment_dir = initialized_lake_environment_dir(workspace, environment)
    spec_path = environment_dir / "spec.json"
    spec_json = read_environment_json(spec_path)
    product_fullspec = environment_active_product(spec_json)
    product_name = _active_product_name_or_none(
        environment_dir,
        spec_json,
        product_fullspec,
    )

    if bootstrapped_product_or_none(spec_json) is not None:
        # Once bootstrap state exists, target restoration is the first invariant.
        # Do not mask a broken target with unrelated product validation errors.
        target = _resolve_bootstrap_target(environment, spec_json, progress)
        validate_bootstrap_product_matches(spec_json, product_fullspec)
        config = deployment_config(product_fullspec)
        validate_config_scheme_tls_consistency(
            config,
            source="spec.stelar.active_product",
        )
    else:
        # For unbootstrapped environments, a bad fullspec should not mutate
        # spec.json as a side effect of a failed bootstrap.
        config = deployment_config(product_fullspec)
        validate_config_scheme_tls_consistency(
            config,
            source="spec.stelar.active_product",
        )
        target = _resolve_bootstrap_target(environment, spec_json, progress)

    context_name = target.context
    namespace = target.namespace
    storage_class_names = configured_storage_class_names(config)
    scheme = deployment_scheme(config)
    cluster_issuer = cluster_issuer_name(config, scheme)

    environment_name = environment_dir.relative_to(workspace.path)
    update_environment_spec_json(
        spec_path,
        environment_name,
        context_name=context_name,
        namespace=namespace,
    )
    spec_json = read_environment_json(spec_path)
    namespace = environment_namespace(spec_json)
    validate_bootstrap_target_matches(spec_json, context_name, namespace)

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

    check_existing_secrets = _guard_against_duplicate_bootstrap(
        namespace,
        config,
        spec_json,
        context_name,
        progress,
    )
    tls_secrets = _manual_tls_secrets_to_apply(environment_dir, config)
    apply_product_secrets(
        namespace,
        config,
        progress,
        check_existing=check_existing_secrets,
    )
    _apply_manual_tls_secrets(
        namespace,
        tls_secrets,
        progress,
        check_existing=check_existing_secrets,
    )
    record_bootstrapped_product(
        spec_path,
        spec_json,
        context_name,
        namespace,
        expected_bootstrap_secret_names(config),
        product_name=product_name,
        product_fullspec=product_fullspec,
    )


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
    product_fullspec = environment_active_product(spec_json)

    target = resolve_environment_target(
        environment,
        spec_json,
        context=context,
        namespace=namespace,
    )

    config = deployment_config(product_fullspec)
    validate_config_scheme_tls_consistency(
        config,
        source="spec.stelar.active_product",
    )
    validate_bootstrap_product_matches(spec_json, product_fullspec)
    storage_class_names = configured_storage_class_names(config)
    scheme = deployment_scheme(config)
    cluster_issuer = cluster_issuer_name(config, scheme)

    _validate_manual_tls_inputs_if_selected(environment_dir, config)

    load_kube_context(target.context)
    run_preflight_checks(
        target.namespace,
        storage_class_names,
        cluster_issuer,
        kube_client_module=kube_client,
        api_exception_type=ApiException,
    )


def _resolve_bootstrap_target(
    environment: str,
    spec_json: dict[str, object],
    progress: ClusterProgress,
) -> EnvironmentTarget:
    return resolve_environment_target(
        environment,
        spec_json,
        infer_missing=True,
        on_inferred_context=lambda context_name: _notify(
            progress,
            "inferred_context",
            context_name,
        ),
        on_inferred_namespace=lambda namespace, context_name: _notify(
            progress,
            "inferred_namespace",
            namespace,
            context_name,
        ),
    )


def _active_product_name_or_none(
    environment_dir: Path,
    spec_json: dict[str, object],
    product_fullspec: dict[str, object],
) -> str | None:
    configured_name = environment_active_product_name_or_none(spec_json)
    if configured_name is not None:
        return configured_name

    suffix = "_fullspec.json"
    for fullspec_path in sorted(environment_dir.glob(f"*{suffix}")):
        product_name = fullspec_path.name[: -len(suffix)]
        if product_name == "product":
            continue
        if not (environment_dir / f"{product_name}.json").is_file():
            continue
        try:
            candidate = read_environment_json(fullspec_path)
        except CommandError:
            continue
        if candidate == product_fullspec:
            return product_name
    return None


def _validate_manual_tls_inputs_if_selected(
    environment_dir: Path,
    config: dict[str, object],
) -> None:
    if not manual_tls_selected(config):
        return

    manual_tls_path = environment_dir / MANUAL_TLS_FILE_NAME
    if not manual_tls_path.exists():
        raise CommandError(
            f"spec.stelar.active_product selects manual_tls, but {manual_tls_path} "
            "does not exist. Generate a sample with `stelarctl lake "
            f"manual-tls-template {manual_tls_path}` and edit it before running "
            "lake verify."
        )
    read_manual_tls_secrets(manual_tls_path, config)


def _notify(progress: ClusterProgress, hook: str, *args: object) -> None:
    getattr(progress, hook, lambda *_args: None)(*args)

def _validate_preflight_mode(preflight: str) -> PreflightMode:
    if preflight not in PREFLIGHT_MODES:
        raise CommandError("Preflight mode must be one of: strict, skip")
    return preflight  # type: ignore[return-value]


def _guard_against_duplicate_bootstrap(
    namespace: str,
    config: dict[str, object],
    spec_json: dict[str, object],
    context_name: str,
    progress: ClusterProgress,
) -> bool:
    secret_names = bootstrap_secret_names(
        spec_json,
        context_name,
        namespace,
        expected_bootstrap_secret_names(config),
    )
    try:
        state = check_secret_existence(namespace, secret_names)
    except SecretReadForbidden as exc:
        _notify(progress, "bootstrap_state_check_forbidden", namespace, str(exc))
        return False

    if state.all_exist:
        _notify(progress, "bootstrap_already_applied", namespace, secret_names)
        raise CommandError(
            "Lake bootstrap appears to have already run in namespace "
            f"{namespace!r}: all required bootstrap Secrets already exist."
        )

    if state.existing:
        raise CommandError(
            "Lake bootstrap found a partial bootstrap state in namespace "
            f"{namespace!r}: {len(state.existing)} required Secrets exist and "
            f"{len(state.missing)} are missing. Refusing to create Secrets into "
            "an inconsistent bootstrap state."
        )

    return True


def _manual_tls_secrets_to_apply(
    environment_dir: Path,
    config: dict[str, object],
) -> list[ManualTlsSecret]:
    if not manual_tls_selected(config):
        return []

    manual_tls_path = environment_dir / MANUAL_TLS_FILE_NAME
    if not manual_tls_path.exists():
        raise CommandError(
            f"spec.stelar.active_product selects manual_tls, but {manual_tls_path} "
            "does not exist. Generate a sample with `stelarctl lake "
            f"manual-tls-template {manual_tls_path}` and edit it before running "
            "lake bootstrap."
        )

    # The fullspec owns the Kubernetes Secret names; manual_tls.yaml owns only
    # local certificate/key paths so operators can rotate files without editing
    # generated configuration.
    return read_manual_tls_secrets(manual_tls_path, config)


def _apply_manual_tls_secrets(
    namespace: str,
    tls_secrets: list[ManualTlsSecret],
    progress: ClusterProgress,
    *,
    check_existing: bool,
) -> None:
    if not tls_secrets:
        return

    core_api = kube_client.CoreV1Api()
    for tls_secret in tls_secrets:
        apply_tls_secret_if_missing(
            core_api,
            namespace,
            tls_secret.name,
            tls_secret.certificate,
            tls_secret.private_key,
            progress,
            check_existing=check_existing,
        )
