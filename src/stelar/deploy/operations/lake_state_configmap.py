"""Cluster-side lake state stored by stelarctl."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from kubernetes import client as kube_client
from kubernetes.client.rest import ApiException

from .common import CommandError, JsonObject
from .progress import ClusterProgress

LAKE_STATE_CONFIGMAP_NAME = "stelar-lake-state"
PRODUCT_NAME_KEY = "product_name"
PRODUCT_FILENAME_KEY = "product_filename"
PRODUCT_JSON_KEY = "product.json"
FULLSPEC_JSON_KEY = "fullspec.json"


@dataclass(frozen=True)
class LakeState:
    """Product metadata recorded in the cluster for a bootstrapped lake."""

    product_name: str | None
    product_filename: str | None
    product: JsonObject | None
    fullspec: JsonObject


def apply_lake_state_configmap(
    namespace: str,
    *,
    product_name: str | None,
    product: JsonObject | None,
    fullspec: JsonObject,
    progress: ClusterProgress,
) -> None:
    """Create the cluster source of truth for a newly bootstrapped lake."""
    core_api = kube_client.CoreV1Api()
    body = lake_state_configmap(namespace, product_name, product, fullspec)
    progress.applying_configmap(LAKE_STATE_CONFIGMAP_NAME)
    try:
        core_api.create_namespaced_config_map(namespace=namespace, body=body)
    except ApiException as exc:
        if getattr(exc, "status", None) == 409:
            raise CommandError(
                f"ConfigMap {LAKE_STATE_CONFIGMAP_NAME!r} already exists in "
                f"namespace {namespace!r}. Refusing to overwrite cluster lake "
                "state; inspect it with `stelarctl lake status ENV` or "
                "unbootstrap the namespace before retrying."
            ) from exc
        if _is_forbidden(exc):
            raise CommandError(
                f"Kubernetes user is not authorized to create ConfigMap "
                f"{LAKE_STATE_CONFIGMAP_NAME!r} in namespace {namespace!r}."
            ) from exc
        raise CommandError(
            f"Could not create ConfigMap {LAKE_STATE_CONFIGMAP_NAME!r} "
            f"in namespace {namespace!r}: {exc}"
        ) from exc
    progress.configmap_applied(LAKE_STATE_CONFIGMAP_NAME)


def read_lake_state_configmap(namespace: str) -> LakeState | None:
    """Read cluster lake state; return None when it is not present."""
    core_api = kube_client.CoreV1Api()
    try:
        configmap = core_api.read_namespaced_config_map(
            LAKE_STATE_CONFIGMAP_NAME,
            namespace,
        )
    except ApiException as exc:
        if getattr(exc, "status", None) == 404:
            return None
        if _is_forbidden(exc):
            raise CommandError(
                f"Kubernetes user is not authorized to read ConfigMap "
                f"{LAKE_STATE_CONFIGMAP_NAME!r} in namespace {namespace!r}."
            ) from exc
        raise CommandError(
            f"Could not read ConfigMap {LAKE_STATE_CONFIGMAP_NAME!r} "
            f"in namespace {namespace!r}: {exc}"
        ) from exc
    return parse_lake_state_configmap(configmap)


def delete_lake_state_configmap(namespace: str) -> bool:
    """Delete cluster lake state; return False when it is already absent."""
    core_api = kube_client.CoreV1Api()
    try:
        core_api.delete_namespaced_config_map(
            LAKE_STATE_CONFIGMAP_NAME,
            namespace,
        )
    except ApiException as exc:
        if getattr(exc, "status", None) == 404:
            return False
        if _is_forbidden(exc):
            raise CommandError(
                f"Kubernetes user is not authorized to delete ConfigMap "
                f"{LAKE_STATE_CONFIGMAP_NAME!r} in namespace {namespace!r}."
            ) from exc
        raise CommandError(
            f"Could not delete ConfigMap {LAKE_STATE_CONFIGMAP_NAME!r} "
            f"in namespace {namespace!r}: {exc}"
        ) from exc
    return True


def lake_state_configmap(
    namespace: str,
    product_name: str | None,
    product: JsonObject | None,
    fullspec: JsonObject,
) -> JsonObject:
    data = {
        FULLSPEC_JSON_KEY: _json_dumps(fullspec),
    }
    if product_name is not None:
        data[PRODUCT_NAME_KEY] = product_name
        data[PRODUCT_FILENAME_KEY] = f"{product_name}.json"
    if product is not None:
        data[PRODUCT_JSON_KEY] = _json_dumps(product)
    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": LAKE_STATE_CONFIGMAP_NAME,
            "namespace": namespace,
            "labels": {
                "app.kubernetes.io/managed-by": "stelarctl",
                "app.kubernetes.io/part-of": "stelar",
            },
        },
        "data": data,
    }


def parse_lake_state_configmap(configmap: Any) -> LakeState:
    data = getattr(configmap, "data", None)
    if not isinstance(data, dict):
        raise CommandError(
            f"ConfigMap {LAKE_STATE_CONFIGMAP_NAME!r} must contain data"
        )
    fullspec = _json_object(data.get(FULLSPEC_JSON_KEY), FULLSPEC_JSON_KEY)
    product_raw = data.get(PRODUCT_JSON_KEY)
    product = _json_object(product_raw, PRODUCT_JSON_KEY) if product_raw else None
    product_name = _optional_string(data.get(PRODUCT_NAME_KEY), PRODUCT_NAME_KEY)
    product_filename = _optional_string(
        data.get(PRODUCT_FILENAME_KEY),
        PRODUCT_FILENAME_KEY,
    )
    return LakeState(product_name, product_filename, product, fullspec)


def _json_object(value: object, key: str) -> JsonObject:
    if not isinstance(value, str) or not value.strip():
        raise CommandError(
            f"ConfigMap {LAKE_STATE_CONFIGMAP_NAME!r} must define {key}"
        )
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise CommandError(
            f"ConfigMap {LAKE_STATE_CONFIGMAP_NAME!r} {key} is invalid JSON: {exc}"
        ) from exc
    if not isinstance(parsed, dict):
        raise CommandError(
            f"ConfigMap {LAKE_STATE_CONFIGMAP_NAME!r} {key} must be a JSON object"
        )
    return parsed


def _optional_string(value: object, key: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise CommandError(
            f"ConfigMap {LAKE_STATE_CONFIGMAP_NAME!r} {key} must be a non-empty string"
        )
    return value.strip()


def _json_dumps(value: JsonObject) -> str:
    return json.dumps(value, sort_keys=True, indent=2)


def _is_forbidden(exc: ApiException) -> bool:
    return getattr(exc, "status", None) == 403
