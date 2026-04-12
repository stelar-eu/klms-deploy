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

CORE_WORKLOADS = {"db", "redis", "minio", "keycloak", "stelarapi", "ckan", "solr", "datapusher"}
FULL_WORKLOADS = {"ontop", "quay", "visualizer", "previewer"}


@dataclass(frozen=True)
class LiveDeployment:
    context: str
    namespace: str
    active: bool
    model: PlatformModel | None
    warnings: list[str]


def infer_live_deployment(context_name: str, namespace: str) -> LiveDeployment:
    config.load_kube_config(context=context_name)

    core_api = client.CoreV1Api()
    apps_api = client.AppsV1Api()
    batch_api = client.BatchV1Api()
    networking_api = client.NetworkingV1Api()

    try:
        namespace_obj = core_api.read_namespace(namespace)
    except client.exceptions.ApiException as exc:
        if exc.status == 404:
            return LiveDeployment(
                context=context_name,
                namespace=namespace,
                active=False,
                model=None,
                warnings=[f"Namespace '{namespace}' does not exist on context '{context_name}'."],
            )
        raise
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
        tier = _infer_tier_from_workloads(workload_names)

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
        tier = "core"
        warnings.append("Tier annotation missing; inferred tier=core from partial live resources.")

    ingress_by_name = {item.metadata.name: item for item in ingresses}
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
    if workload_names & FULL_WORKLOADS:
        return "full"
    if workload_names & CORE_WORKLOADS:
        return "core"
    return None


def _infer_network(
    ingress_by_name: dict[str, Any],
    warnings: list[str],
) -> tuple[str, dict[str, str], str, str, str | None, str]:
    primary = ingress_by_name.get("stelar")
    kc = ingress_by_name.get("kc")
    s3 = ingress_by_name.get("s3")
    reg = ingress_by_name.get("reg")
    anchor = primary or kc or s3 or reg
    if anchor is None or not anchor.spec.rules:
        raise ValueError("Unable to infer STELAR DNS configuration from ingress resources.")

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
        warnings.append("Ingress class missing on ingress; defaulting to nginx.")
    return root, subdomains, scheme, tls_mode, issuer, ingress_class


def _subdomain_from_ingress(ingress: Any, root: str, fallback: str) -> str:
    if ingress is None or not ingress.spec.rules:
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
    by_name = {item.metadata.name: item for item in configmaps}
    api_config = by_name.get("api-config-map")
    data = api_config.data if api_config and api_config.data else {}
    llm_enabled = data.get("ENABLE_LLM_SEARCH", "false").lower() == "true" or "llmsearch" in workload_names
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
    deploys = {item.metadata.name: item for item in deployments}
    states = {item.metadata.name: item for item in statefulsets}

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
        key_name = "key" if expected_name == "session-secret-key" else "password"
        secrets.append({"name": name, "data": {key_name: None}})
    if llm_enabled:
        # The live cluster can expose the optional secret name, but PlatformModel does not store it yet.
        pass
    return secrets


def _secret_name_from_env(resource: Any, env_name: str) -> str | None:
    if resource is None:
        return None
    containers = resource.spec.template.spec.containers or []
    for container in containers:
        for env in container.env or []:
            if env.name != env_name:
                continue
            value_from = getattr(env, "value_from", None)
            secret_ref = getattr(value_from, "secret_key_ref", None) if value_from else None
            if secret_ref and secret_ref.name:
                return secret_ref.name
    return None
