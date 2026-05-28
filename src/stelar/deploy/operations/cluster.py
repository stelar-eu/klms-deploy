"""Business logic for `init-lake cluster`."""

from __future__ import annotations

import base64
import random
import string
from pathlib import Path
from typing import Any, Literal

from kubernetes import client as kube_client
from kubernetes import config as kube_config
from kubernetes.client.rest import ApiException

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
from .progress import ClusterProgress

INGRESS_CLASS_NAME = "nginx"
INGRESS_NGINX_CONTROLLER_SELECTORS = (
    "app.kubernetes.io/component=controller",
    "app.kubernetes.io/name=ingress-nginx",
    "app.kubernetes.io/name=rke2-ingress-nginx",
)
CERT_MANAGER_NAMESPACE = "cert-manager"
CERT_MANAGER_CRDS = [
    "certificates.cert-manager.io",
    "clusterissuers.cert-manager.io",
]
CERT_MANAGER_DEPLOYMENTS = [
    "cert-manager",
    "cert-manager-cainjector",
    "cert-manager-webhook",
]
STORAGE_CLASS_FIELDS = (
    ("dynamicStorageClass",),
    ("provisioning_storage_class", "dynamic_volume_storage_class"),
)
PRODUCT_SECRET_FIELDS = (
    (
        "postgres",
        "POSTGRES_DB_PASSWORD_SECRET_NAME",
        "POSTGRES_DB_PASSWORD",
        "password",
    ),
    ("postgres", "CKAN_DB_PASSWORD_SECRET_NAME", "CKAN_DB_PASSWORD", "password"),
    (
        "postgres",
        "KEYCLOAK_DB_PASSWORD_SECRET_NAME",
        "KEYCLOAK_DB_PASSWORD",
        "password",
    ),
    (
        "postgres",
        "DATASTORE_DB_PASSWORD_SECRET_NAME",
        "DATASTORE_DB_PASSWORD",
        "password",
    ),
    ("postgres", "QUAY_DB_PASSWORD_SECRET_NAME", "QUAY_DB_PASSWORD", "password"),
    (
        "keycloak",
        "KEYCLOAK_ROOT_PASSWORD_SECRET_NAME",
        "KEYCLOAK_ROOT_PASSWORD",
        "password",
    ),
    ("api", "SMTP_PASSWORD_SECRET_NAME", "SMTP_PASSWORD", "password"),
    ("api", "SESSION_SECRET_KEY_SECRET_NAME", "SESSION_SECRET_KEY", "key"),
    ("ckan", "CKAN_ADMIN_PASSWORD_SECRET_NAME", "CKAN_ADMIN_PASSWORD", "password"),
    ("minio", "MINIO_ROOT_PASSWORD_SECRET_NAME", "MINIO_ROOT_PASSWORD", "password"),
)
OPTIONAL_PRODUCT_SECRET_FIELDS = (
    ("llm_search", "GROQ_API_KEY_SECRET_NAME", "GROQ_API_KEY", "key"),
)
CKAN_AUTH_SECRET_NAME = "ckan-auth-secret"
PreflightMode = Literal["strict", "skip"]
PREFLIGHT_MODES = ("strict", "skip")
PREFLIGHT_SKIP_HINT = (
    "Your current Kubernetes user does not have access to perform this "
    "read-only preflight check. Ask a cluster administrator for read access, "
    "or rerun with --skip-preflight to bypass prerequisite checks and let "
    "the deployment fail later if the cluster is not ready."
)


class PreflightAccessError(CommandError):
    """Raised when RBAC prevents a read-only preflight check."""


def _preflight_access_denied(check: str, exc: ApiException) -> PreflightAccessError:
    return PreflightAccessError(
        f"Cannot perform {check} preflight check: Kubernetes API returned "
        f"{exc.status} {exc.reason or 'Forbidden'}. {PREFLIGHT_SKIP_HINT}"
    )


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
        _run_preflight_checks(
            namespace,
            storage_class_names,
            scheme,
            cluster_issuer,
        )

    _apply_environment_secrets(namespace, spec, progress)


def _validate_preflight_mode(preflight: str) -> PreflightMode:
    if preflight not in PREFLIGHT_MODES:
        raise CommandError("Preflight mode must be one of: strict, skip")
    return preflight  # type: ignore[return-value]


def _run_preflight_checks(
    namespace: str,
    storage_class_names: list[str],
    scheme: str,
    cluster_issuer: str,
) -> None:
    _validate_namespace(namespace)
    for storage_class_name in storage_class_names:
        _validate_storage_class(storage_class_name)
    _validate_ingress_class(INGRESS_CLASS_NAME)
    _validate_ingress_controller(INGRESS_CLASS_NAME)
    if cluster_issuer:
        _validate_cert_manager()
        _validate_cluster_issuer(cluster_issuer)


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

    for secret_name, secret_data in _product_secrets(spec):
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


def _product_secrets(spec: JsonObject) -> list[tuple[str, dict[str, str]]]:
    secrets = [
        _secret_from_product_spec(spec, section, name_key, value_key, data_key)
        for section, name_key, value_key, data_key in PRODUCT_SECRET_FIELDS
    ]

    for section, name_key, value_key, data_key in OPTIONAL_PRODUCT_SECRET_FIELDS:
        if section in spec:
            secrets.append(
                _secret_from_product_spec(
                    spec,
                    section,
                    name_key,
                    value_key,
                    data_key,
                )
            )

    return secrets


def _secret_from_product_spec(
    spec: JsonObject,
    section: str,
    name_key: str,
    value_key: str,
    data_key: str,
) -> tuple[str, dict[str, str]]:
    section_config = _product_spec_section(spec, section)
    secret_name = _required_product_spec_string(section_config, section, name_key)
    secret_value = _required_product_spec_string(section_config, section, value_key)
    return secret_name, {data_key: secret_value}


def _product_spec_section(spec: JsonObject, section: str) -> JsonObject:
    value = spec.get(section)
    if not isinstance(value, dict):
        raise CommandError(f"Product spec must contain a {section} object")
    return value


def _required_product_spec_string(
    section_config: JsonObject,
    section: str,
    key: str,
) -> str:
    value = section_config.get(key)
    if not isinstance(value, str) or not value:
        raise CommandError(
            f"Product spec must define {section}.{key} "
            "as a non-empty string"
        )
    return value


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

    _create_secret(
        core_api,
        namespace,
        secret_name,
        {
            "session-key": _generate_random_string(40, 8, "-"),
            "jwt-key": _generate_jwt_key(),
        },
        progress,
    )


def _secret_exists(core_api: Any, namespace: str, secret_name: str) -> bool:
    try:
        core_api.read_namespaced_secret(secret_name, namespace)
        return True
    except ApiException as exc:
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
    secret = _kubernetes_secret(secret_name, namespace, data)
    progress.secret_generated(secret_name)
    progress.applying_secret(secret_name)
    try:
        core_api.create_namespaced_secret(namespace=namespace, body=secret)
    except ApiException as exc:
        if exc.status == 409:
            progress.secret_exists(secret_name)
            return
        raise CommandError(
            f"Could not create Secret {secret_name!r} in namespace "
            f"{namespace!r}: {exc}"
        ) from exc
    progress.secret_applied(secret_name)


def _kubernetes_secret(
    secret_name: str,
    namespace: str,
    data: dict[str, str],
) -> JsonObject:
    encoded_data = {
        key: base64.b64encode(value.encode("utf-8")).decode("utf-8")
        for key, value in data.items()
    }
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": secret_name,
            "namespace": namespace,
        },
        "type": "Opaque",
        "data": encoded_data,
    }


def _generate_jwt_key(length: int = 43) -> str:
    return f"string:{_random_token(length)}"


def _generate_random_string(
    length: int = 40,
    chunk_size: int = 8,
    separator: str = "-",
) -> str:
    raw_string = _random_token(length)
    chunks = [
        raw_string[index : index + chunk_size]
        for index in range(0, length, chunk_size)
    ]
    return separator.join(chunks)


def _random_token(length: int) -> str:
    rng = random.SystemRandom()
    characters = string.ascii_letters + string.digits
    return "".join(rng.choice(characters) for _ in range(length))


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


def _validate_namespace(namespace: str) -> None:
    core_api = kube_client.CoreV1Api()
    try:
        core_api.read_namespace(namespace)
    except ApiException as exc:
        if _is_forbidden(exc):
            raise _preflight_access_denied(f"Namespace {namespace!r}", exc) from exc
        if exc.status == 404:
            raise CommandError(
                f"Namespace {namespace!r} does not exist in the selected cluster. "
                "Create the namespace or update product.json spec.namespace."
            ) from exc
        raise CommandError(
            f"Could not validate Namespace {namespace!r}: {exc}"
        ) from exc


def _validate_storage_class(storage_class_name: str) -> None:
    storage_api = kube_client.StorageV1Api()
    try:
        storage_api.read_storage_class(storage_class_name)
    except ApiException as exc:
        if _is_forbidden(exc):
            raise _preflight_access_denied(
                f"StorageClass {storage_class_name!r}",
                exc,
            ) from exc
        if exc.status == 404:
            raise CommandError(
                f"StorageClass {storage_class_name!r} does not exist in the "
                "selected cluster. Update product_fullspec.json storage class "
                "fields or install the StorageClass."
            ) from exc
        raise CommandError(
            f"Could not validate StorageClass {storage_class_name!r}: {exc}"
        ) from exc


def _validate_ingress_class(ingress_class_name: str) -> None:
    networking_api = kube_client.NetworkingV1Api()
    try:
        networking_api.read_ingress_class(ingress_class_name)
    except ApiException as exc:
        if _is_forbidden(exc):
            raise _preflight_access_denied(
                f"IngressClass {ingress_class_name!r}",
                exc,
            ) from exc
        if exc.status == 404:
            raise CommandError(
                f"IngressClass {ingress_class_name!r} does not exist in the "
                "selected cluster. Install/configure the ingress class expected "
                "by the product."
            ) from exc
        raise CommandError(
            f"Could not validate IngressClass {ingress_class_name!r}: {exc}"
        ) from exc


def _validate_ingress_controller(ingress_class_name: str) -> None:
    core_api = kube_client.CoreV1Api()
    for selector in INGRESS_NGINX_CONTROLLER_SELECTORS:
        try:
            pods = core_api.list_pod_for_all_namespaces(label_selector=selector)
        except ApiException as exc:
            if _is_forbidden(exc):
                raise _preflight_access_denied(
                    "ingress-nginx controller pod discovery",
                    exc,
                ) from exc
            raise CommandError(
                f"Could not validate ingress-nginx controller for "
                f"IngressClass {ingress_class_name!r}: {exc}"
            ) from exc

        if any(
            _pod_matches_ingress_nginx_controller(pod) and _pod_is_ready(pod)
            for pod in pods.items or []
        ):
            return

    try:
        pods = core_api.list_pod_for_all_namespaces()
    except ApiException as exc:
        if _is_forbidden(exc):
            raise _preflight_access_denied(
                "ingress-nginx controller pod discovery",
                exc,
            ) from exc
        raise CommandError(
            f"Could not validate ingress-nginx controller for "
            f"IngressClass {ingress_class_name!r}: {exc}"
        ) from exc

    if any(
        _pod_matches_ingress_nginx_controller(pod) and _pod_is_ready(pod)
        for pod in pods.items or []
    ):
        return

    raise CommandError(
        f"No Ready ingress-nginx controller pod found for "
        f"IngressClass {ingress_class_name!r}. Install/start ingress-nginx or "
        "update the product/cluster ingress setup."
    )


def _pod_matches_ingress_nginx_controller(pod: Any) -> bool:
    metadata = getattr(pod, "metadata", None)
    labels = getattr(metadata, "labels", None) or {}
    label_name = labels.get("app.kubernetes.io/name", "")
    pod_name = getattr(metadata, "name", "") or ""
    return "ingress-nginx" in label_name or "ingress-nginx" in pod_name


def _pod_is_ready(pod: Any) -> bool:
    status = getattr(pod, "status", None)
    if getattr(status, "phase", None) != "Running":
        return False

    return any(
        getattr(condition, "type", None) == "Ready"
        and getattr(condition, "status", None) == "True"
        for condition in getattr(status, "conditions", []) or []
    )


def _validate_cert_manager() -> None:
    apiextensions_api = kube_client.ApiextensionsV1Api()
    for crd_name in CERT_MANAGER_CRDS:
        try:
            apiextensions_api.read_custom_resource_definition(crd_name)
        except ApiException as exc:
            if _is_forbidden(exc):
                raise _preflight_access_denied(
                    f"cert-manager CRD {crd_name!r}",
                    exc,
                ) from exc
            if exc.status == 404:
                raise CommandError(
                    f"cert-manager CRD {crd_name!r} does not exist. Install "
                    "cert-manager or generate a product that does not require "
                    "cert-manager-managed TLS."
                ) from exc
            raise CommandError(
                f"Could not validate cert-manager CRD {crd_name!r}: {exc}"
            ) from exc

    apps_api = kube_client.AppsV1Api()
    for deployment_name in CERT_MANAGER_DEPLOYMENTS:
        try:
            deployment = apps_api.read_namespaced_deployment_status(
                deployment_name,
                CERT_MANAGER_NAMESPACE,
            )
        except ApiException as exc:
            if _is_forbidden(exc):
                raise _preflight_access_denied(
                    f"cert-manager Deployment {deployment_name!r}",
                    exc,
                ) from exc
            if exc.status == 404:
                raise CommandError(
                    f"cert-manager Deployment {deployment_name!r} does not exist "
                    f"in namespace {CERT_MANAGER_NAMESPACE!r}. Install "
                    "cert-manager or generate a product that does not require "
                    "cert-manager-managed TLS."
                ) from exc
            raise CommandError(
                f"Could not validate cert-manager Deployment "
                f"{deployment_name!r}: {exc}"
            ) from exc

        desired_replicas = deployment.spec.replicas or 1
        available_replicas = deployment.status.available_replicas or 0
        if available_replicas < desired_replicas:
            raise CommandError(
                f"cert-manager Deployment {deployment_name!r} is not Ready. "
                "Wait for cert-manager to become Ready before deploying HTTPS."
            )


def _validate_cluster_issuer(cluster_issuer: str) -> None:
    custom_objects_api = kube_client.CustomObjectsApi()
    try:
        issuer = custom_objects_api.get_cluster_custom_object(
            group="cert-manager.io",
            version="v1",
            plural="clusterissuers",
            name=cluster_issuer,
        )
    except ApiException as exc:
        if _is_forbidden(exc):
            raise _preflight_access_denied(
                f"ClusterIssuer {cluster_issuer!r}",
                exc,
            ) from exc
        if exc.status == 404:
            raise CommandError(
                f"ClusterIssuer {cluster_issuer!r} does not exist in the "
                "selected cluster. Create the issuer or update the product "
                "ingress.cert_manager.ClusterIssuer value."
            ) from exc
        raise CommandError(
            f"Could not validate ClusterIssuer {cluster_issuer!r}: {exc}"
        ) from exc

    if not _is_ready_condition_true(issuer):
        raise CommandError(
            f"ClusterIssuer {cluster_issuer!r} is not Ready. Fix the issuer "
            "before deploying HTTPS."
        )


def _is_ready_condition_true(resource: JsonObject) -> bool:
    status = resource.get("status", {})
    if not isinstance(status, dict):
        return False
    conditions = status.get("conditions", [])
    if not isinstance(conditions, list):
        return False
    return any(
        isinstance(condition, dict)
        and condition.get("type") == "Ready"
        and condition.get("status") == "True"
        for condition in conditions
    )


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
