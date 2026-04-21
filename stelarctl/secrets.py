"""Kubernetes Secret management for model-defined and generated secrets."""

import base64
import random
import string

from kubernetes import client, config

try:
    from .platform_model import PlatformModel
except ImportError:
    from platform_model import PlatformModel


def _random_string(length: int, chunk_size: int = 8, separator: str = "-") -> str:
    """Generate a chunked random alphanumeric value for generated secrets."""
    characters = string.ascii_letters + string.digits
    raw = "".join(random.choices(characters, k=length))
    # Chunking makes generated values easier to inspect in Kubernetes during
    # debugging while keeping the underlying entropy length unchanged.
    chunks = [raw[i:i + chunk_size] for i in range(0, length, chunk_size)]
    return separator.join(chunks)


def _encode(data: dict) -> dict:
    """Base64-encode secret data for the Kubernetes API."""
    # The Kubernetes Secret API expects base64-encoded string values under
    # `data`. stelarctl accepts plaintext in the platform model and encodes at
    # the API boundary.
    return {
        k: base64.b64encode(v.encode("utf-8")).decode("utf-8")
        for k, v in data.items()
    }


def _apply_secret(v1: client.CoreV1Api, name: str, namespace: str, data: dict):
    """Create or replace an Opaque secret in the target namespace."""
    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": {
                "app.kubernetes.io/managed-by": "stelarctl",
                "app.kubernetes.io/part-of": "stelar",
            },
        },
        "type": "Opaque",
        "data": _encode(data),
    }
    try:
        v1.create_namespaced_secret(namespace=namespace, body=secret)
    except client.exceptions.ApiException as exc:
        if exc.status != 409:
            raise
        # Replacing on conflict makes repeated deploys idempotent and lets model
        # secret changes flow into the cluster before Tanka applies workloads.
        v1.replace_namespaced_secret(name=name, namespace=namespace, body=secret)


def apply_secrets(model: PlatformModel):
    """Apply user-defined secrets from the platform model."""
    config.load_kube_config(context=model.k8s_context)
    v1 = client.CoreV1Api()

    # Only keys explicitly present in the model are sent. Optional None values
    # are omitted so inferred live models can be compared without leaking values
    # back into the cluster.
    for secret in model.secrets:
        _apply_secret(v1, secret.name, model.namespace, secret.data.model_dump(exclude_none=True))


def apply_generated_secrets(model: PlatformModel):
    """Apply system-generated secrets that are not part of the platform model."""
    config.load_kube_config(context=model.k8s_context)
    v1 = client.CoreV1Api()

    # CKAN needs auth keys whose values are operational details rather than
    # operator-supplied model fields. They are regenerated on deploy and applied
    # before manifests that reference ckan-auth-secret are rolled out.
    session_key = _random_string(40)
    jwt_key = "string:" + _random_string(43, chunk_size=43)

    _apply_secret(v1, "ckan-auth-secret", model.namespace, {
        "session-key": session_key,
        "jwt-key": jwt_key,
    })


def delete_secrets(model: PlatformModel):
    """Delete all secrets in the model's namespace."""
    config.load_kube_config(context=model.k8s_context)
    v1 = client.CoreV1Api()

    # This is intentionally namespace-wide because generated and third-party
    # secret names are not all represented in PlatformModel. The CLI prompt
    # should be treated as destructive.
    secrets = v1.list_namespaced_secret(namespace=model.namespace)
    for secret in secrets.items:
        v1.delete_namespaced_secret(name=secret.metadata.name, namespace=model.namespace)
