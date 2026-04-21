"""Infer STELAR deployment metadata from live Kubernetes resources.

Live inference is intentionally best-effort. It provides enough model-shaped
data for status and deploy planning, but it is not expected to reproduce every
field from the original YAML exactly, especially secret values and some storage
intent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kubernetes import client, config

try:
    from .platform_model import PlatformModel
except ImportError:
    from platform_model import PlatformModel


STELAR_TIER_ANNOTATION = "stelar.eu/tier"
STELAR_PLATFORM_ANNOTATION = "stelar.eu/platform"
STELAR_AUTHOR_ANNOTATION = "stelar.eu/author"

# Workload names are the primary signal for active-deployment detection and tier
# inference. Keep these names aligned with the Jsonnet component names generated
# by the tier libraries.
CORE_WORKLOADS = {"db", "redis", "minio", "keycloak", "stelarapi", "ckan", "solr", "datapusher"}
FULL_WORKLOADS = {"ontop", "quay", "visualizer", "previewer"}


@dataclass(frozen=True)
class LiveDeployment:
    """Best-effort reconstruction of a deployment from cluster state.

    `active` answers whether known STELAR resources are present. `model` is only
    set when enough resources exist to build a PlatformModel-compatible view.
    `warnings` carries inference fallbacks that should be shown to operators but
    are not necessarily fatal.
    """

    context: str
    namespace: str
    active: bool
    model: PlatformModel | None
    warnings: list[str]


def infer_live_deployment(context_name: str, namespace: str) -> LiveDeployment:
    """Infer whether STELAR is active and reconstruct a comparable model."""
    config.load_kube_config(context=context_name)

    # Use direct Kubernetes API reads instead of shelling out to kubectl. The
    # returned objects preserve enough structured metadata to rebuild a partial
    # PlatformModel for comparison and status collection.
    core_api = client.CoreV1Api()
    apps_api = client.AppsV1Api()
    batch_api = client.BatchV1Api()
    networking_api = client.NetworkingV1Api()

    try:
        namespace_obj = core_api.read_namespace(namespace)
    except client.exceptions.ApiException as exc:
        if exc.status == 404:
            # A missing namespace is not an exceptional status-query result. It
            # simply means there is no active deployment at this target.
            return LiveDeployment(
                context=context_name,
                namespace=namespace,
                active=False,
                model=None,
                warnings=[f"Namespace '{namespace}' does not exist on context '{context_name}'."],
            )
        raise
    # All reads below are namespace-scoped. stelarctl does not need cluster-wide
    # workload scans to infer a single deployment target.
    deployments = apps_api.list_namespaced_deployment(namespace=namespace).items
    statefulsets = apps_api.list_namespaced_stateful_set(namespace=namespace).items
    ingresses = networking_api.list_namespaced_ingress(namespace=namespace).items
    configmaps = core_api.list_namespaced_config_map(namespace=namespace).items
    pvcs = core_api.list_namespaced_persistent_volume_claim(namespace=namespace).items
    jobs = batch_api.list_namespaced_job(namespace=namespace).items

    workload_names = {item.metadata.name for item in deployments} | {item.metadata.name for item in statefulsets}
    annotations = namespace_obj.metadata.annotations or {}

    tier = annotations.get(STELAR_TIER_ANNOTATION)
    if tier not in {"core", "full"}:
        # Older deployments or partially manually-created namespaces may not
        # have annotations. Workload names are enough to infer the tier in most
        # cases, though warnings are emitted when inference is incomplete.
        tier = _infer_tier_from_workloads(workload_names)

    # Namespace annotations alone are not enough: teardown can leave the
    # namespace alive, so active deployment detection is based on resources.
    has_stelar_resources = bool(workload_names & (CORE_WORKLOADS | FULL_WORKLOADS)) or any(
        ingress.metadata.name in {"stelar", "kc", "s3", "reg"} for ingress in ingresses
    ) or any(
        configmap.metadata.name in {"api-config-map", "kc-cmap", "minio-cmap", "ckan-config", "registry-config"}
        for configmap in configmaps
    )
    active = has_stelar_resources
    if not active:
        return LiveDeployment(context=context_name, namespace=namespace, active=False, model=None, warnings=[])

    warnings: list[str] = []
    if tier is None:
        # Pick the smaller tier when the available resource set is too partial
        # to prove full. This keeps status usable while surfacing the uncertainty.
        tier = "core"
        warnings.append("Tier annotation missing; inferred tier=core from partial live resources.")

    ingress_by_name = {item.metadata.name: item for item in ingresses}
    # Network and config inference deliberately reconstruct only the fields the
    # PlatformModel needs for comparison and status. It is not a full manifest
    # reverse-engineering pass.
    root, subdomains, scheme, tls_mode, issuer, ingress_class = _infer_network(ingress_by_name, warnings)
    app_config = _infer_app_config(configmaps, workload_names, scheme=scheme, root=root, primary_subdomain=subdomains["primary"])
    storage_config = _infer_storage(pvcs)
    platform = annotations.get(STELAR_PLATFORM_ANNOTATION, context_name)
    author = annotations.get(STELAR_AUTHOR_ANNOTATION, "unknown")
    secrets = _infer_secret_names(deployments, statefulsets, tier, app_config["enable_llm_search"])

    model = PlatformModel(
        platform=platform,
        k8s_context=context_name,
        namespace=namespace,
        author=author,
        tier=tier,
        infrastructure={
            "storage": storage_config,
            "ingress_class": ingress_class,
            "tls": {
                "mode": tls_mode,
                "issuer": issuer,
            },
        },
        dns={
            "root": root,
            "scheme": scheme,
            "primary": subdomains["primary"],
            "keycloak": subdomains["keycloak"],
            "minio": subdomains["minio"],
            "registry": subdomains["registry"],
        },
        config=app_config,
        secrets=secrets,
    )
    return LiveDeployment(context=context_name, namespace=namespace, active=True, model=model, warnings=warnings)


def _infer_tier_from_workloads(workload_names: set[str]) -> str | None:
    """Infer `core` or `full` from known workload names."""
    if workload_names & FULL_WORKLOADS:
        return "full"
    if workload_names & CORE_WORKLOADS:
        return "core"
    return None


def _infer_network(
    ingress_by_name: dict[str, Any],
    warnings: list[str],
) -> tuple[str, dict[str, str], str, str, str | None, str]:
    """Infer DNS, scheme, TLS mode, issuer, and ingress class from ingresses."""
    primary = ingress_by_name.get("stelar")
    kc = ingress_by_name.get("kc")
    s3 = ingress_by_name.get("s3")
    reg = ingress_by_name.get("reg")
    anchor = primary or kc or s3 or reg
    if anchor is None or not anchor.spec.rules:
        raise ValueError("Unable to infer STELAR DNS configuration from ingress resources.")

    # Any STELAR ingress can establish the root domain. Prefer the primary
    # ingress when present, but use a secondary ingress so status can still work
    # while resources are being created or deleted.
    primary_host = anchor.spec.rules[0].host
    primary_parts = primary_host.split(".")
    if len(primary_parts) < 2:
        raise ValueError(f"Unable to infer root domain from ingress host: {primary_host}")

    root = ".".join(primary_parts[1:])
    subdomains = {
        "primary": primary_parts[0],
        "keycloak": _subdomain_from_ingress(kc, root, "kc"),
        "minio": _subdomain_from_ingress(s3, root, "minio"),
        "registry": _subdomain_from_ingress(reg, root, "img"),
    }

    # TLS mode is inferred from the actual ingress shape: no TLS block means
    # plain HTTP, a cert-manager annotation means cert-manager, and remaining TLS
    # cases are treated as manually supplied certificates.
    scheme = "https" if anchor.spec.tls else "http"
    annotations = anchor.metadata.annotations or {}
    issuer = annotations.get("cert-manager.io/cluster-issuer")
    if scheme == "http":
        tls_mode = "none"
        issuer = None
    elif issuer:
        tls_mode = "cert-manager"
    else:
        tls_mode = "manual"

    ingress_class = anchor.spec.ingress_class_name or "nginx"
    if anchor.spec.ingress_class_name is None:
        # Existing manifests historically used nginx as the implicit class, so
        # preserve that behavior while warning that the live object is incomplete.
        warnings.append("Ingress class missing on ingress; defaulting to nginx.")
    return root, subdomains, scheme, tls_mode, issuer, ingress_class


def _subdomain_from_ingress(ingress: Any, root: str, fallback: str) -> str:
    """Return the subdomain prefix for an ingress host under `root`."""
    if ingress is None or not ingress.spec.rules:
        # Missing optional ingresses should not make the whole deployment
        # invisible. Fall back to the model defaults used by DNSConfig.
        return fallback
    host = ingress.spec.rules[0].host
    suffix = f".{root}"
    return host[: -len(suffix)] if host.endswith(suffix) else fallback


def _infer_app_config(
    configmaps: list[Any],
    workload_names: set[str],
    *,
    scheme: str,
    root: str,
    primary_subdomain: str,
) -> dict[str, Any]:
    """Infer application config values from ConfigMaps and workload presence."""
    by_name = {item.metadata.name: item for item in configmaps}
    api_config = by_name.get("api-config-map")
    data = api_config.data if api_config and api_config.data else {}
    # LLM search can be inferred either from the API config flag or from the
    # optional workload itself. This handles deployments where ConfigMaps lag
    # behind workloads during apply.
    llm_enabled = data.get("ENABLE_LLM_SEARCH", "false").lower() == "true" or "llmsearch" in workload_names
    # The console URL has a stable default derivable from primary ingress data,
    # so status remains useful even if the API ConfigMap is not available yet.
    s3_console_url = data.get("S3_CONSOLE_URL") or f"{scheme}://{primary_subdomain}.{root}/s3/login"

    return {
        "smtp_server": data.get("SMTP_SERVER", ""),
        "smtp_port": data.get("SMTP_PORT", ""),
        "smtp_username": data.get("SMTP_USERNAME", ""),
        "s3_console_url": s3_console_url,
        "enable_llm_search": llm_enabled,
        "groq_api_url": None if data.get("GROQ_API_URL") in {None, "null", ""} else data.get("GROQ_API_URL"),
        "groq_api_model": None if data.get("GROQ_MODEL") in {None, "null", ""} else data.get("GROQ_MODEL"),
    }


def _infer_storage(pvcs: list[Any]) -> dict[str, str]:
    """Infer storage classes from PVCs, returning empty values when absent."""
    # PVCs expose the class actually used by bound claims, not the original
    # model intent. Multiple classes are sorted to keep output deterministic.
    classes = sorted(
        {
            pvc.spec.storage_class_name
            for pvc in pvcs
            if pvc.spec.storage_class_name
        }
    )
    if not classes:
        return {
            "dynamic_class": "",
            "provisioning_class": "",
        }
    if len(classes) == 1:
        return {
            "dynamic_class": classes[0],
            "provisioning_class": classes[0],
        }
    return {
        "dynamic_class": classes[0],
        "provisioning_class": classes[1],
    }


def _infer_secret_names(
    deployments: list[Any],
    statefulsets: list[Any],
    tier: str,
    llm_enabled: bool,
) -> list[dict[str, Any]]:
    """Infer model secret names from workload environment references."""
    deploys = {item.metadata.name: item for item in deployments}
    states = {item.metadata.name: item for item in statefulsets}

    # The keys are the canonical logical secret names expected by generator.py.
    # The values are the actual Secret names referenced by live workload env
    # vars. When a workload is absent, fall back to the canonical name so the
    # reconstructed PlatformModel remains valid enough for comparison.
    mapping = {
        "postgresdb-secret": _secret_name_from_env(states.get("db"), "POSTGRES_PASSWORD"),
        "ckandb-secret": _secret_name_from_env(states.get("db"), "CKAN_DB_PASSWORD"),
        "keycloakdb-secret": _secret_name_from_env(states.get("db"), "KEYCLOAK_DB_PASSWORD"),
        "datastoredb-secret": _secret_name_from_env(states.get("db"), "DATASTORE_READONLY_PASSWORD"),
        "keycloakroot-secret": _secret_name_from_env(deploys.get("keycloak"), "KEYCLOAK_ADMIN_PASSWORD"),
        "smtpapi-secret": _secret_name_from_env(deploys.get("stelarapi"), "SMTP_PASSWORD"),
        "ckanadmin-secret": _secret_name_from_env(deploys.get("ckan"), "CKAN_SYSADMIN_PASSWORD"),
        "minioroot-secret": _secret_name_from_env(states.get("minio"), "MINIO_ROOT_PASSWORD"),
        "session-secret-key": _secret_name_from_env(deploys.get("stelarapi"), "SESSION_SECRET_KEY"),
        "quaydb-secret": _secret_name_from_env(states.get("db"), "QUAY_DB_PASSWORD") if tier == "full" else "quaydb-secret",
    }

    secrets: list[dict[str, Any]] = []
    for expected_name, actual_name in mapping.items():
        name = actual_name or expected_name
        # PlatformModel can represent either `password` or `key`. Values are
        # intentionally None because live inference should not recover or compare
        # plaintext secret content.
        key_name = "key" if expected_name == "session-secret-key" else "password"
        secrets.append({"name": name, "data": {key_name: None}})
    if llm_enabled:
        # The live cluster can expose the optional LLM secret name through
        # workload env refs, but PlatformModel does not store that secret yet.
        # Keep this branch explicit so the extension point is visible when the
        # model grows support for it.
        pass
    return secrets


def _secret_name_from_env(resource: Any, env_name: str) -> str | None:
    """Read a secret name from a container environment variable reference."""
    if resource is None:
        return None
    containers = resource.spec.template.spec.containers or []
    for container in containers:
        for env in container.env or []:
            if env.name != env_name:
                continue
            # Only secretKeyRef-backed variables carry a reusable Secret name.
            # Literal values and config-map references are ignored here.
            value_from = getattr(env, "value_from", None)
            secret_ref = getattr(value_from, "secret_key_ref", None) if value_from else None
            if secret_ref and secret_ref.name:
                return secret_ref.name
    return None
