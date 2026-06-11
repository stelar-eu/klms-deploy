"""Kubernetes Secret application helpers for lake bootstrap."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kubernetes import client as kube_client
from kubernetes.client.rest import ApiException

from .common import CommandError, JsonObject
from .progress import ClusterProgress
from .secret_resources import (
    BootstrapSecretValues,
    ckan_auth_secret_data,
    ckan_auth_secret_name,
    generate_bootstrap_secret_values,
    kubernetes_secret,
    kubernetes_tls_secret,
    product_secrets,
)


@dataclass(frozen=True)
class SecretExistenceResult:
    """Existing and missing Secret names for a bootstrap state check."""

    existing: tuple[str, ...]
    missing: tuple[str, ...]

    @property
    def all_exist(self) -> bool:
        return not self.missing


class SecretReadForbidden(CommandError):
    """Raised when RBAC prevents reading Secrets for bootstrap state."""


def apply_product_secrets(
    namespace: str,
    config: JsonObject,
    progress: ClusterProgress,
    *,
    check_existing: bool = True,
    secret_values: BootstrapSecretValues | None = None,
) -> None:
    """Create required fullspec-derived Kubernetes Secrets when missing."""
    core_api = kube_client.CoreV1Api()
    values = secret_values or generate_bootstrap_secret_values()

    for secret_name, secret_data in product_secrets(config, values):
        if check_existing:
            apply_secret_if_missing(
                core_api,
                namespace,
                secret_name,
                secret_data,
                progress,
            )
        else:
            create_secret(
                core_api,
                namespace,
                secret_name,
                secret_data,
                progress,
                allow_conflict=False,
            )

    if check_existing:
        apply_ckan_auth_secret_if_missing(
            core_api,
            namespace,
            ckan_auth_secret_name(config),
            progress,
            values,
        )
    else:
        create_secret(
            core_api,
            namespace,
            ckan_auth_secret_name(config),
            ckan_auth_secret_data(values),
            progress,
            allow_conflict=False,
        )


def apply_tls_secret_if_missing(
    core_api: Any,
    namespace: str,
    secret_name: str,
    cert_pem: str,
    key_pem: str,
    progress: ClusterProgress,
    *,
    check_existing: bool = True,
) -> None:
    """Create a Kubernetes TLS Secret when it is missing."""
    if not check_existing:
        create_tls_secret(
            core_api,
            namespace,
            secret_name,
            cert_pem,
            key_pem,
            progress,
            allow_conflict=False,
        )
        return

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
    secret_values: BootstrapSecretValues,
) -> None:
    """Create the generated CKAN auth Secret when it is missing."""
    if secret_exists(core_api, namespace, secret_name):
        progress.secret_exists(secret_name)
        return

    create_secret(
        core_api,
        namespace,
        secret_name,
        ckan_auth_secret_data(secret_values),
        progress,
    )


def check_secret_existence(
    namespace: str,
    secret_names: tuple[str, ...],
) -> SecretExistenceResult:
    """Read expected bootstrap Secrets and classify them as existing or missing."""
    core_api = kube_client.CoreV1Api()
    existing = []
    missing = []
    for secret_name in secret_names:
        exists = secret_exists(core_api, namespace, secret_name)
        if exists:
            existing.append(secret_name)
        else:
            missing.append(secret_name)
    return SecretExistenceResult(tuple(existing), tuple(missing))


def secret_exists(core_api: Any, namespace: str, secret_name: str) -> bool:
    """Return whether a namespaced Secret exists, mapping Kubernetes errors."""
    try:
        core_api.read_namespaced_secret(secret_name, namespace)
        return True
    except ApiException as exc:
        if is_forbidden(exc):
            raise SecretReadForbidden(
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
    *,
    allow_conflict: bool = True,
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
            if not allow_conflict:
                raise CommandError(
                    f"Secret {secret_name!r} already exists in namespace "
                    f"{namespace!r}, but stelarctl could not validate bootstrap "
                    "state before creating Secrets. Refusing to record bootstrap "
                    "state because existing Secret values may belong to another "
                    "bootstrap. Rerun with a Kubernetes user allowed to get "
                    "secrets or purge the existing bootstrap Secrets intentionally."
                ) from exc
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
    *,
    allow_conflict: bool = True,
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
            if not allow_conflict:
                raise CommandError(
                    f"Manual TLS Secret {secret_name!r} already exists in "
                    f"namespace {namespace!r}, but stelarctl could not validate "
                    "bootstrap state before creating Secrets. Refusing to record "
                    "bootstrap state because existing Secret values may belong "
                    "to another bootstrap. Rerun with a Kubernetes user allowed "
                    "to get secrets or purge the existing bootstrap Secrets "
                    "intentionally."
                ) from exc
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
