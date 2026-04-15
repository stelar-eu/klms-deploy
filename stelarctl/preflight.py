from collections.abc import Callable

import typer
from kubernetes import client, config

from platform_model import PlatformModel


def validate_model_against_cluster(model: PlatformModel) -> bool:
    """Return True when cluster-side prerequisites referenced by the model exist."""
    _require_context(model.k8s_context)

    try:
        config.load_kube_config(context=model.k8s_context)
    except Exception as exc:
        raise typer.BadParameter(f"Could not load Kubernetes context '{model.k8s_context}': {exc}") from exc

    errors: list[str] = []
    core = client.CoreV1Api()
    storage = client.StorageV1Api()
    networking = client.NetworkingV1Api()

    _collect_required_resource(
        errors,
        field="namespace",
        kind="Namespace",
        name=model.namespace,
        read=lambda: core.read_namespace(name=model.namespace),
    )
    _collect_required_resource(
        errors,
        field="infrastructure.storage.dynamic_class",
        kind="StorageClass",
        name=model.infrastructure.storage.dynamic_class,
        read=lambda: storage.read_storage_class(name=model.infrastructure.storage.dynamic_class),
    )
    _collect_required_resource(
        errors,
        field="infrastructure.storage.provisioning_class",
        kind="StorageClass",
        name=model.infrastructure.storage.provisioning_class,
        read=lambda: storage.read_storage_class(name=model.infrastructure.storage.provisioning_class),
    )
    _collect_required_resource(
        errors,
        field="infrastructure.ingress_class",
        kind="IngressClass",
        name=model.infrastructure.ingress_class,
        read=lambda: networking.read_ingress_class(name=model.infrastructure.ingress_class),
    )

    if model.infrastructure.tls.mode == "cert-manager":
        _collect_cert_manager_issuer(errors, client.CustomObjectsApi(), model)

    if errors:
        raise typer.BadParameter("Model does not match cluster:\n- " + "\n- ".join(errors))

    return True


def _require_context(context: str) -> None:
    try:
        contexts, _active = config.list_kube_config_contexts()
    except Exception as exc:
        raise typer.BadParameter(f"Could not read kubeconfig contexts: {exc}") from exc

    if not contexts:
        raise typer.BadParameter("No Kubernetes contexts found in kubeconfig.")

    names = {entry.get("name") for entry in contexts}
    if context not in names:
        raise typer.BadParameter(f"k8s_context '{context}' was not found in kubeconfig.")


def _collect_required_resource(
    errors: list[str],
    *,
    field: str,
    kind: str,
    name: str,
    read: Callable[[], object],
) -> None:
    try:
        read()
    except Exception as exc:
        if _api_status(exc) == 404:
            errors.append(f"{field}: {kind} '{name}' was not found.")
            return
        errors.append(f"{field}: could not validate {kind} '{name}': {_api_error_message(exc)}")


def _collect_cert_manager_issuer(errors: list[str], custom_api, model: PlatformModel) -> None:
    issuer = model.infrastructure.tls.issuer
    if issuer is None:
        errors.append("infrastructure.tls.issuer: issuer is required when tls.mode is cert-manager.")
        return

    cluster_issuer_found, cluster_issuer_error = _custom_object_lookup(
        custom_api.get_cluster_custom_object,
        group="cert-manager.io",
        version="v1",
        plural="clusterissuers",
        name=issuer,
    )
    if cluster_issuer_found:
        return

    namespaced_issuer_found, namespaced_issuer_error = _custom_object_lookup(
        custom_api.get_namespaced_custom_object,
        group="cert-manager.io",
        version="v1",
        namespace=model.namespace,
        plural="issuers",
        name=issuer,
    )
    if namespaced_issuer_found:
        return

    validation_errors = [error for error in [cluster_issuer_error, namespaced_issuer_error] if error]
    if validation_errors:
        errors.append(
            "infrastructure.tls.issuer: could not validate cert-manager issuer: "
            + "; ".join(validation_errors)
        )
        return

    errors.append(
        "infrastructure.tls.issuer: cert-manager ClusterIssuer "
        f"'{issuer}' or Issuer '{issuer}' in namespace '{model.namespace}' was not found."
    )


def _custom_object_lookup(call: Callable[..., object], **kwargs: str) -> tuple[bool, str | None]:
    try:
        call(**kwargs)
        return True, None
    except Exception as exc:
        if _api_status(exc) == 404:
            return False, None
        return False, _api_error_message(exc)


def _api_status(exc: Exception) -> int | None:
    return getattr(exc, "status", None)


def _api_error_message(exc: Exception) -> str:
    status = _api_status(exc)
    reason = getattr(exc, "reason", None)
    if status and reason:
        return f"Kubernetes API error {status}: {reason}"
    return str(exc)
