import base64
import random
import string

from kubernetes import client, config
from platform_model import PlatformModel


def _random_string(length: int, chunk_size: int = 8, separator: str = "-") -> str:
    characters = string.ascii_letters + string.digits
    raw = "".join(random.choices(characters, k=length))
    chunks = [raw[i:i + chunk_size] for i in range(0, length, chunk_size)]
    return separator.join(chunks)


def _encode(data: dict) -> dict:
    return {
        k: base64.b64encode(v.encode("utf-8")).decode("utf-8")
        for k, v in data.items()
    }


def _apply_secret(v1: client.CoreV1Api, name: str, namespace: str, data: dict):
    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": name, "namespace": namespace},
        "type": "Opaque",
        "data": _encode(data),
    }
    v1.create_namespaced_secret(namespace=namespace, body=secret)


def apply_secrets(model: PlatformModel):
    """Apply user-defined secrets from the platform model."""
    config.load_kube_config(context=model.k8s_context)
    v1 = client.CoreV1Api()

    for secret in model.secrets:
        _apply_secret(v1, secret.name, model.namespace, secret.data.model_dump(exclude_none=True))


def apply_generated_secrets(model: PlatformModel):
    """Apply system-generated secrets that are not part of the platform model."""
    config.load_kube_config(context=model.k8s_context)
    v1 = client.CoreV1Api()

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

    secrets = v1.list_namespaced_secret(namespace=model.namespace)
    for secret in secrets.items:
        v1.delete_namespaced_secret(name=secret.metadata.name, namespace=model.namespace)
