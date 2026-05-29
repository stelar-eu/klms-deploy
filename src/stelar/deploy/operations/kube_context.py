"""Kubectl context loading and Kubernetes client authentication helpers."""

from __future__ import annotations

from kubernetes import client as kube_client
from kubernetes import config as kube_config

from .common import CommandError


def resolve_kube_context(context: str | None) -> str:
    """Return an explicit or active kubectl context after validating it exists."""
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


def load_kube_context(context_name: str) -> None:
    """Load a kubectl context and normalize token auth for the Kubernetes client."""
    try:
        kube_config.load_kube_config(context=context_name)
        normalize_bearer_token_auth()
    except Exception as exc:
        raise CommandError(
            f"Could not load kubectl context {context_name!r}: {exc}"
        ) from exc


def normalize_bearer_token_auth() -> None:
    """Expose kubeconfig authorization tokens under the key expected by the client."""
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
