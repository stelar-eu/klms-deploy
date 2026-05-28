"""Business logic for `init-lake cluster`."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from kubernetes import client as kube_client
from kubernetes import config as kube_config
from kubernetes.client.rest import ApiException

from .cluster_preflight import PreflightAccessError, run_preflight_checks
from .common import (
    CommandError,
    JsonObject,
    ensure_object,
    existing_object,
    product_author,
    product_spec,
    read_environment_json,
    validate_workspace,
    write_environment_json,
)
from .fullspec_validation import validate_config_scheme_tls_consistency
from .lake_environment import complete_lake_environment_dir
from .manual_tls import (
    MANUAL_TLS_FILE_NAME,
    manual_tls_selected,
    read_manual_tls_secrets,
)
from .progress import ClusterProgress
from .secret_resources import (
    CKAN_AUTH_SECRET_NAME,
    ckan_auth_secret_data,
    kubernetes_secret,
    kubernetes_tls_secret,
    product_secrets,
)

STORAGE_CLASS_FIELDS = (
    ("dynamicStorageClass",),
    ("provisioning_storage_class", "dynamic_volume_storage_class"),
)
PreflightMode = Literal["strict", "skip"]
PREFLIGHT_MODES = ("strict", "skip")
def _is_forbidden(exc: ApiException) -> bool:
    return exc.status == 403


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

    context_name = _resolve_kube_context(context)
    environment_name = environment_dir.relative_to(workspace.path)
    _update_environment_spec_json(
        environment_dir / "spec.json",
        environment_name,
        context_name,
        product_data,
    )
    spec_json = read_environment_json(environment_dir / "spec.json")
    namespace = _environment_namespace(spec_json)
    config = _deployment_config(product_fullspec)
    validate_config_scheme_tls_consistency(config)
    storage_class_names = _configured_storage_class_names(config)
    scheme = _deployment_scheme(config)
    cluster_issuer = _cluster_issuer_name(config, scheme)

    _load_kube_context(context_name)
    if preflight == "strict":
        run_preflight_checks(
            namespace,
            storage_class_names,
            cluster_issuer,
            kube_client_module=kube_client,
            api_exception_type=ApiException,
        )

    _apply_environment_secrets(namespace, spec, progress)
    _apply_manual_tls_secrets_if_present(environment_dir, namespace, config, progress)


def _validate_preflight_mode(preflight: str) -> PreflightMode:
    if preflight not in PREFLIGHT_MODES:
        raise CommandError("Preflight mode must be one of: strict, skip")
    return preflight  # type: ignore[return-value]


def _environment_namespace(spec_json: JsonObject) -> str:
    spec = existing_object(spec_json, "spec")
    namespace = spec.get("namespace")
    if not isinstance(namespace, str) or not namespace:
        raise CommandError("Environment spec.json must define a non-empty namespace")
    return namespace


def _deployment_config(product_fullspec: JsonObject) -> JsonObject:
    config = product_fullspec.get("klms")
    if not isinstance(config, dict):
        raise CommandError("product_fullspec.json must contain a klms object")
    return config


def _configured_storage_class_names(config: JsonObject) -> list[str]:
    storage_class_names = []
    seen_storage_class_names = set()

    # Check both PVC storage classes used by the render. The provisioning class
    # has an older fullspec key that is kept as an alias for compatibility.
    for field_names in STORAGE_CLASS_FIELDS:
        storage_class_name = _storage_class_name(config, field_names)
        if storage_class_name in seen_storage_class_names:
            continue
        storage_class_names.append(storage_class_name)
        seen_storage_class_names.add(storage_class_name)

    return storage_class_names


def _storage_class_name(config: JsonObject, field_names: tuple[str, ...]) -> str:
    for field_name in field_names:
        storage_class_name = config.get(field_name)
        if storage_class_name is None:
            continue
        if not isinstance(storage_class_name, str) or not storage_class_name:
            raise CommandError(
                f"product_fullspec.json must define {field_name} "
                "as a non-empty string"
            )
        return storage_class_name

    if len(field_names) == 1:
        expected_field = field_names[0]
    else:
        expected_field = f"{field_names[0]} or {', '.join(field_names[1:])}"
    raise CommandError(f"product_fullspec.json must define {expected_field}")


def _deployment_scheme(config: JsonObject) -> str:
    scheme = config.get("SCHEME", "http")
    if scheme not in {"http", "https"}:
        raise CommandError("product_fullspec.json must define SCHEME as http or https")
    return scheme


def _cluster_issuer_name(config: JsonObject, scheme: str) -> str:
    ingress = config.get("ingress")
    if ingress is None:
        if scheme == "http":
            return ""
        raise CommandError("product_fullspec.json must define ingress")
    if not isinstance(ingress, dict):
        raise CommandError("product_fullspec.json must define ingress as an object")

    tls = ingress.get("tls", [])
    if not isinstance(tls, list) or not all(isinstance(item, str) for item in tls):
        raise CommandError("product_fullspec.json must define ingress.tls as a list")
    if "cert_manager" not in tls:
        return ""

    cert_manager = ingress.get("cert_manager")
    if not isinstance(cert_manager, dict):
        raise CommandError(
            "product_fullspec.json must define ingress.cert_manager when "
            "ingress.tls selects cert_manager"
        )
    cluster_issuer = cert_manager.get("ClusterIssuer")
    if not isinstance(cluster_issuer, str) or not cluster_issuer:
        raise CommandError(
            "product_fullspec.json must define ingress.cert_manager.ClusterIssuer "
            "when ingress.tls selects cert_manager"
        )
    return cluster_issuer


def _apply_environment_secrets(
    namespace: str,
    spec: JsonObject,
    progress: ClusterProgress,
) -> None:
    core_api = kube_client.CoreV1Api()

    for secret_name, secret_data in product_secrets(spec):
        _apply_secret_if_missing(
            core_api,
            namespace,
            secret_name,
            secret_data,
            progress,
        )

    _apply_ckan_auth_secret_if_missing(
        core_api,
        namespace,
        CKAN_AUTH_SECRET_NAME,
        progress,
    )


def _apply_manual_tls_secrets_if_present(
    environment_dir: Path,
    namespace: str,
    config: JsonObject,
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

    tls_secrets = read_manual_tls_secrets(manual_tls_path, config)
    core_api = kube_client.CoreV1Api()
    for tls_secret in tls_secrets:
        _apply_tls_secret_if_missing(
            core_api,
            namespace,
            tls_secret.name,
            tls_secret.certificate,
            tls_secret.private_key,
            progress,
        )


def _apply_tls_secret_if_missing(
    core_api: Any,
    namespace: str,
    secret_name: str,
    cert_pem: str,
    key_pem: str,
    progress: ClusterProgress,
) -> None:
    if _secret_exists(core_api, namespace, secret_name):
        progress.secret_exists(secret_name)
        return

    _create_tls_secret(core_api, namespace, secret_name, cert_pem, key_pem, progress)


def _apply_secret_if_missing(
    core_api: Any,
    namespace: str,
    secret_name: str,
    data: dict[str, str],
    progress: ClusterProgress,
) -> None:
    if _secret_exists(core_api, namespace, secret_name):
        progress.secret_exists(secret_name)
        return

    _create_secret(core_api, namespace, secret_name, data, progress)


def _apply_ckan_auth_secret_if_missing(
    core_api: Any,
    namespace: str,
    secret_name: str,
    progress: ClusterProgress,
) -> None:
    if _secret_exists(core_api, namespace, secret_name):
        progress.secret_exists(secret_name)
        return

    _create_secret(core_api, namespace, secret_name, ckan_auth_secret_data(), progress)


def _secret_exists(core_api: Any, namespace: str, secret_name: str) -> bool:
    try:
        core_api.read_namespaced_secret(secret_name, namespace)
        return True
    except ApiException as exc:
        if _is_forbidden(exc):
            raise CommandError(
                f"Kubernetes user is not authorized to validate Secret "
                f"{secret_name!r} in namespace {namespace!r}. Ask a cluster "
                "administrator for permission to get secrets or rerun with an "
                "authorized context."
            ) from exc
        if exc.status != 404:
            raise CommandError(
                f"Could not validate Secret {secret_name!r} in namespace "
                f"{namespace!r}: {exc}"
            ) from exc
        return False


def _create_secret(
    core_api: Any,
    namespace: str,
    secret_name: str,
    data: dict[str, str],
    progress: ClusterProgress,
) -> None:
    progress.generating_secret(secret_name)
    secret = kubernetes_secret(secret_name, namespace, data)
    progress.secret_generated(secret_name)
    progress.applying_secret(secret_name)
    try:
        core_api.create_namespaced_secret(namespace=namespace, body=secret)
    except ApiException as exc:
        if exc.status == 409:
            progress.secret_exists(secret_name)
            return
        if _is_forbidden(exc):
            raise CommandError(
                f"Kubernetes user is not authorized to create Secret "
                f"{secret_name!r} in namespace {namespace!r}. Ask a cluster "
                "administrator for permission to create secrets or rerun with "
                "an authorized context."
            ) from exc
        raise CommandError(
            f"Could not create Secret {secret_name!r} in namespace "
            f"{namespace!r}: {exc}"
        ) from exc
    progress.secret_applied(secret_name)


def _create_tls_secret(
    core_api: Any,
    namespace: str,
    secret_name: str,
    cert_pem: str,
    key_pem: str,
    progress: ClusterProgress,
) -> None:
    progress.generating_secret(secret_name)
    secret = kubernetes_tls_secret(secret_name, namespace, cert_pem, key_pem)
    progress.secret_generated(secret_name)
    progress.applying_secret(secret_name)
    try:
        core_api.create_namespaced_secret(namespace=namespace, body=secret)
    except ApiException as exc:
        if exc.status == 409:
            progress.secret_exists(secret_name)
            return
        if _is_forbidden(exc):
            raise CommandError(
                f"Kubernetes user is not authorized to create manual TLS "
                f"Secret {secret_name!r} in namespace {namespace!r}. Ask a "
                "cluster administrator for permission to create secrets or "
                "rerun with an authorized context."
            ) from exc
        raise CommandError(
            f"Could not create manual TLS Secret {secret_name!r} in namespace "
            f"{namespace!r}: {exc}"
        ) from exc
    progress.secret_applied(secret_name)


def _load_kube_context(context_name: str) -> None:
    try:
        kube_config.load_kube_config(context=context_name)
        _normalize_bearer_token_auth()
    except Exception as exc:
        raise CommandError(
            f"Could not load kubectl context {context_name!r}: {exc}"
        ) from exc


def _normalize_bearer_token_auth() -> None:
    config = kube_client.Configuration.get_default_copy()
    authorization = config.api_key.get("authorization")
    if not authorization or "BearerToken" in config.api_key:
        return

    if authorization.startswith("Bearer "):
        config.api_key["BearerToken"] = authorization.removeprefix("Bearer ")
        config.api_key_prefix["BearerToken"] = "Bearer"
    else:
        config.api_key["BearerToken"] = authorization
        config.api_key_prefix.setdefault("BearerToken", "Bearer")

    kube_client.Configuration.set_default(config)


def _resolve_kube_context(context: str | None) -> str:
    try:
        contexts, active_context = kube_config.list_kube_config_contexts()
    except Exception as exc:
        raise CommandError(f"Could not load kubectl contexts: {exc}") from exc

    context_names = {
        kube_context["name"]
        for kube_context in contexts or []
        if isinstance(kube_context, dict) and "name" in kube_context
    }

    if context is None:
        if not isinstance(active_context, dict) or not active_context.get("name"):
            raise CommandError("No active kubectl context found")
        context = active_context["name"]

    if context not in context_names:
        raise CommandError(f"Kubectl context {context!r} does not exist")

    return context


def _update_environment_spec_json(
    spec_path: Path,
    environment_name: Path,
    context_name: str,
    product_data: JsonObject,
) -> None:
    spec_json = read_environment_json(spec_path)
    spec = product_spec(product_data)
    namespace = spec.get("namespace")
    if not isinstance(namespace, str) or not namespace:
        raise CommandError("Product spec must define a non-empty namespace")

    environment_name_text = environment_name.as_posix()
    metadata = ensure_object(spec_json, "metadata")
    metadata["name"] = environment_name_text
    metadata["namespace"] = f"{environment_name_text}/main.jsonnet"

    tk_spec = ensure_object(spec_json, "spec")
    tk_spec["contextNames"] = [context_name]
    tk_spec["namespace"] = namespace
    tk_spec.setdefault("expectVersions", {})
    tk_spec["injectLabels"] = True

    resource_defaults = ensure_object(tk_spec, "resourceDefaults")
    labels = ensure_object(resource_defaults, "labels")
    labels.setdefault("app.kubernetes.io/managed-by", "tanka")
    labels.setdefault("app.kubernetes.io/part-of", "stelar")
    labels.setdefault("stelar.deployment", "main")

    annotations = ensure_object(resource_defaults, "annotations")
    author = product_author(product_data)
    if author is not None:
        annotations["stelar.eu/author"] = author
    elif annotations.get("stelar.eu/author") == "<author>":
        del annotations["stelar.eu/author"]

    write_environment_json(spec_path, spec_json)
