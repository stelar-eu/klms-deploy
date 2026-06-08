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
    bootstrapped_target_fields_or_none,
    record_bootstrapped_product,
    reject_bootstrap_target_overrides,
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
    environment_context_name_or_none,
    environment_namespace,
    environment_namespace_or_none,
    update_environment_spec_json,
)
from .fullspec_validation import validate_config_scheme_tls_consistency
from .kube_context import load_kube_context, resolve_kube_context, resolve_kube_namespace
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
    product_data: dict[str, object] = {}
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
        context_name, namespace = _resolve_bootstrap_target(spec_json, progress)
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
        context_name, namespace = _resolve_bootstrap_target(spec_json, progress)

    storage_class_names = configured_storage_class_names(config)
    scheme = deployment_scheme(config)
    cluster_issuer = cluster_issuer_name(config, scheme)

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

    bootstrapped_target = bootstrapped_target_fields_or_none(spec_json)
    if bootstrapped_target is not None:
        validate_bootstrap_target_matches(spec_json, *bootstrapped_target)
        reject_bootstrap_target_overrides(
            spec_json,
            context=context,
            namespace=namespace,
        )
        context_name = resolve_kube_context(bootstrapped_target[0])
        check_namespace = bootstrapped_target[1]
    else:
        context_name = _required_check_context(environment, spec_json, context)
        check_namespace = _required_check_namespace(environment, spec_json, namespace)

    config = deployment_config(product_fullspec)
    validate_config_scheme_tls_consistency(
        config,
        source="spec.stelar.active_product",
    )
    validate_bootstrap_target_matches(spec_json, context_name, check_namespace)
    validate_bootstrap_product_matches(spec_json, product_fullspec)
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


def _resolve_bootstrap_target(
    spec_json: dict[str, object],
    progress: ClusterProgress,
) -> tuple[str, str]:
    configured_context = environment_context_name_or_none(spec_json)
    configured_namespace = environment_namespace_or_none(spec_json)

    bootstrapped_target = bootstrapped_target_fields_or_none(spec_json)
    if bootstrapped_target is not None:
        validate_bootstrap_target_matches(spec_json, *bootstrapped_target)
        context_name = resolve_kube_context(bootstrapped_target[0])
        namespace = bootstrapped_target[1]
        return context_name, namespace

    if configured_context is None:
        context_name = resolve_kube_context(None)
        _notify(progress, "inferred_context", context_name)
    else:
        context_name = resolve_kube_context(configured_context)

    if configured_namespace is None:
        namespace = resolve_kube_namespace(context_name)
        _notify(progress, "inferred_namespace", namespace, context_name)
    else:
        namespace = configured_namespace

    return context_name, namespace


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
            "Rerun with --context CONTEXT, or let `stelarctl lake bootstrap` "
            "infer and write it."
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
            "Rerun with --namespace NAMESPACE, or let `stelarctl lake bootstrap` "
            "infer and write it."
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
