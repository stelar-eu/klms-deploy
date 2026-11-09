"""Plaintext credential export for a completed lake bootstrap."""

from __future__ import annotations

import os
from pathlib import Path

from .common import CommandError, JsonObject, read_environment_json, validate_workspace
from .deployment_config import deployment_config, deployment_scheme
from .environment_spec import (
    environment_active_product,
    environment_context_name,
    environment_namespace,
)
from .lake_environment import initialized_lake_environment_dir
from .secret_resources import BootstrapSecretValues, validate_bootstrap_secret_values


def validate_bootstrap_credentials_output(path: Path) -> Path:
    """Validate a credential export destination without creating it."""
    if path.suffix.lower() != ".txt":
        raise CommandError(
            "Bootstrap credentials output must use a .txt filename"
        )
    if path.exists():
        raise CommandError(
            f"Credentials file {path} already exists; refusing to overwrite it"
        )
    parent = path.parent
    if not parent.exists():
        raise CommandError(
            f"Credentials file parent directory {parent} does not exist"
        )
    if not parent.is_dir():
        raise CommandError(
            f"Credentials file parent path {parent} is not a directory"
        )
    return path


def write_environment_bootstrap_credentials(
    environment: str,
    workspace_path: Path,
    output_path: Path,
    secret_values: BootstrapSecretValues,
) -> Path:
    """Write credentials for an environment after bootstrap has succeeded."""
    workspace = validate_workspace(workspace_path)
    environment_dir = initialized_lake_environment_dir(workspace, environment)
    spec_json = read_environment_json(environment_dir / "spec.json")
    config = deployment_config(environment_active_product(spec_json))
    content = render_bootstrap_credentials(
        environment=environment_dir.relative_to(workspace.path).as_posix(),
        context=environment_context_name(spec_json),
        namespace=environment_namespace(spec_json),
        config=config,
        secret_values=secret_values,
    )
    _write_private_text_file(output_path, content)
    return output_path


def render_bootstrap_credentials(
    *,
    environment: str,
    context: str,
    namespace: str,
    config: JsonObject,
    secret_values: BootstrapSecretValues,
) -> str:
    """Render the human-facing credentials created by lake bootstrap."""
    validate_bootstrap_secret_values(secret_values)

    scheme = deployment_scheme(config)
    root_domain = _required_string(config, "ROOT_DOMAIN", "klms")
    primary_subdomain = _required_string(config, "PRIMARY_SUBDOMAIN", "klms")
    primary_url = f"{scheme}://{primary_subdomain}.{root_domain}"

    ckan = _required_object(config, "ckan", "klms")
    ckan_username = _required_string(ckan, "CKAN_SYSADMIN_NAME", "klms.ckan")
    ckan_root_path = _required_path(ckan, "CKAN__ROOT_PATH", "klms.ckan")

    keycloak = _required_object(config, "keycloak", "klms")
    keycloak_username = _required_string(
        keycloak,
        "KEYCLOAK_ADMIN",
        "klms.keycloak",
    )
    keycloak_subdomain = _required_string(
        keycloak,
        "SUBDOMAIN",
        "klms.keycloak",
    )
    keycloak_realm = _required_string(keycloak, "REALM", "klms.keycloak")
    keycloak_url = f"{scheme}://{keycloak_subdomain}.{root_domain}"

    minio = _required_object(config, "minio", "klms")
    minio_username = _required_string(minio, "MINIO_ROOT_USER", "klms.minio")
    minio_console_url = _required_string(
        minio,
        "S3_CONSOLE_URL",
        "klms.minio",
    )
    minio_api_url = _required_string(minio, "API_DOMAIN", "klms.minio")

    quay = _required_object(config, "quay", "klms")
    quay_subdomain = _required_string(quay, "SUBDOMAIN", "klms.quay")
    quay_url = f"{scheme}://{quay_subdomain}.{root_domain}"

    return (
        "STELAR bootstrap credentials\n"
        "============================\n"
        f"Environment: {environment}\n"
        f"Kubernetes context: {context}\n"
        f"Kubernetes namespace: {namespace}\n\n"
        "SECURITY WARNING: This file contains plaintext credentials. "
        "Keep it private and delete it when it is no longer needed.\n\n"
        "[STELAR KLMS]\n"
        f"URL: {primary_url}\n"
        "Authentication: Keycloak SSO\n"
        f"Username: {keycloak_username}\n"
        f"Password: {secret_values.keycloak_root_password}\n\n"
        "[CKAN local administration]\n"
        f"URL: {primary_url}{ckan_root_path}/user/login\n"
        "Authentication: CKAN internal login\n"
        f"Username: {ckan_username}\n"
        f"Password: {secret_values.ckan_admin_password}\n\n"
        "[Keycloak administration]\n"
        f"URL: {keycloak_url}/admin/{keycloak_realm}/console/\n"
        f"Username: {keycloak_username}\n"
        f"Password: {secret_values.keycloak_root_password}\n\n"
        "[MinIO console]\n"
        f"URL: {minio_console_url}\n"
        f"API URL: {minio_api_url}\n"
        f"Username: {minio_username}\n"
        f"Password: {secret_values.minio_root_password}\n\n"
        "[Quay registry]\n"
        f"URL: {quay_url}\n"
        "Authentication: Keycloak SSO\n"
        f"Username: {keycloak_username}\n"
        f"Password: {secret_values.keycloak_root_password}\n"
        "Note: Registry push/pull access also depends on the configured "
        "Keycloak roles.\n\n"
        "Other STELAR services do not receive a separate human username and "
        "password from lake bootstrap. They use SSO, service credentials, or "
        "component-specific configuration.\n"
    )


def _write_private_text_file(path: Path, content: str) -> None:
    validate_bootstrap_credentials_output(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW

    try:
        file_descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise CommandError(f"Could not create credentials file {path}: {exc}") from exc

    try:
        if os.name == "posix":
            os.fchmod(file_descriptor, 0o600)
    except OSError as exc:
        os.close(file_descriptor)
        _remove_partial_file(path)
        raise CommandError(f"Could not secure credentials file {path}: {exc}") from exc

    try:
        with os.fdopen(
            file_descriptor,
            "w",
            encoding="utf-8",
            newline="\n",
        ) as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
    except (OSError, UnicodeError) as exc:
        _remove_partial_file(path)
        raise CommandError(f"Could not write credentials file {path}: {exc}") from exc


def _remove_partial_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _required_object(data: JsonObject, key: str, source: str) -> JsonObject:
    value = data.get(key)
    if not isinstance(value, dict):
        raise CommandError(
            f"Credential export requires {source}.{key} to be an object"
        )
    return value


def _required_string(data: JsonObject, key: str, source: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CommandError(
            f"Credential export requires {source}.{key} to be a non-empty string"
        )
    return value.strip()


def _required_path(data: JsonObject, key: str, source: str) -> str:
    value = _required_string(data, key, source).rstrip("/")
    if not value.startswith("/"):
        raise CommandError(
            f"Credential export requires {source}.{key} to start with '/'"
        )
    return value
