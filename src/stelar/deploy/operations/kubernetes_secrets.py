"""Kubernetes Secret application helpers for lake bootstrap."""

from __future__ import annotations

from typing import Any

from kubernetes import client as kube_client
from kubernetes.client.rest import ApiException

from .common import CommandError, JsonObject
from .progress import ClusterProgress
from .secret_resources import (
    CKAN_AUTH_SECRET_NAME,
    ckan_auth_secret_data,
    kubernetes_secret,
    kubernetes_tls_secret,
    product_secrets,
)


def apply_product_secrets(
    namespace: str,
    spec: JsonObject,
    progress: ClusterProgress,
) -> None:
    """Create required product-derived Kubernetes Secrets when missing."""
    core_api = kube_client.CoreV1Api()

    for secret_name, secret_data in product_secrets(spec):
        apply_secret_if_missing(
            core_api,
            namespace,
            secret_name,
            secret_data,
            progress,
        )

    apply_ckan_auth_secret_if_missing(
        core_api,
        namespace,
        CKAN_AUTH_SECRET_NAME,
        progress,
    )


def apply_tls_secret_if_missing(
    core_api: Any,
    namespace: str,
    secret_name: str,
    cert_pem: str,
    key_pem: str,
    progress: ClusterProgress,
) -> None:
    """Create a Kubernetes TLS Secret when it is missing."""
    if secret_exists(core_api, namespace, secret_name):
        progress.secret_exists(secret_name)
        return

    create_tls_secret(core_api, namespace, secret_name, cert_pem, key_pem, progress)


def apply_secret_if_missing(
    core_api: Any,
    namespace: str,
    secret_name: str,
    data: dict[str, str],
    progress: ClusterProgress,
) -> None:
    """Create an opaque Kubernetes Secret when it is missing."""
    if secret_exists(core_api, namespace, secret_name):
        progress.secret_exists(secret_name)
        return

    create_secret(core_api, namespace, secret_name, data, progress)


def apply_ckan_auth_secret_if_missing(
    core_api: Any,
    namespace: str,
    secret_name: str,
    progress: ClusterProgress,
) -> None:
    """Create the generated CKAN auth Secret when it is missing."""
    if secret_exists(core_api, namespace, secret_name):
        progress.secret_exists(secret_name)
        return

    create_secret(core_api, namespace, secret_name, ckan_auth_secret_data(), progress)


def secret_exists(core_api: Any, namespace: str, secret_name: str) -> bool:
    """Return whether a namespaced Secret exists, mapping Kubernetes errors."""
    try:
        core_api.read_namespaced_secret(secret_name, namespace)
        return True
    except ApiException as exc:
        if is_forbidden(exc):
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


def create_secret(
    core_api: Any,
    namespace: str,
    secret_name: str,
    data: dict[str, str],
    progress: ClusterProgress,
) -> None:
    """Create an opaque Kubernetes Secret and report progress."""
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
        if is_forbidden(exc):
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


def create_tls_secret(
    core_api: Any,
    namespace: str,
    secret_name: str,
    cert_pem: str,
    key_pem: str,
    progress: ClusterProgress,
) -> None:
    """Create a Kubernetes TLS Secret and report progress."""
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
        if is_forbidden(exc):
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


def is_forbidden(exc: ApiException) -> bool:
    """Return true when Kubernetes rejected the request because of RBAC."""
    return exc.status == 403
