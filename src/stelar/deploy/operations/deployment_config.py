"""Validation and accessors for generated KLMS deployment configuration."""

from __future__ import annotations

from .common import CommandError, JsonObject

STORAGE_CLASS_FIELDS = (
    ("dynamicStorageClass",),
    ("provisioning_storage_class", "dynamic_volume_storage_class"),
)


def deployment_config(product_fullspec: JsonObject) -> JsonObject:
    """Return the KLMS object from product_fullspec.json."""
    config = product_fullspec.get("klms")
    if not isinstance(config, dict):
        raise CommandError("product_fullspec.json must contain a klms object")
    return config


def configured_storage_class_names(config: JsonObject) -> list[str]:
    """Return distinct storage classes referenced by the generated config."""
    storage_class_names = []
    seen_storage_class_names = set()

    # Check both PVC storage classes used by the render. The provisioning class
    # has an older fullspec key that is kept as an alias for compatibility.
    for field_names in STORAGE_CLASS_FIELDS:
        storage_class_name = storage_class_name_from(config, field_names)
        if storage_class_name in seen_storage_class_names:
            continue
        storage_class_names.append(storage_class_name)
        seen_storage_class_names.add(storage_class_name)

    return storage_class_names


def storage_class_name_from(config: JsonObject, field_names: tuple[str, ...]) -> str:
    """Read a required storage class value from one of the accepted field names."""
    for field_name in field_names:
        storage_class_name = config.get(field_name)
        if storage_class_name is None:
            continue
        if not isinstance(storage_class_name, str) or not storage_class_name:
            raise CommandError(
                f"product_fullspec.json must define {field_name} "
                "as a non-empty string"
            )
        return storage_class_name

    if len(field_names) == 1:
        expected_field = field_names[0]
    else:
        expected_field = f"{field_names[0]} or {', '.join(field_names[1:])}"
    raise CommandError(f"product_fullspec.json must define {expected_field}")


def deployment_scheme(config: JsonObject) -> str:
    """Return the configured public URL scheme."""
    scheme = config.get("SCHEME", "http")
    if scheme not in {"http", "https"}:
        raise CommandError("product_fullspec.json must define SCHEME as http or https")
    return scheme


def cluster_issuer_name(config: JsonObject, scheme: str) -> str:
    """Return the ClusterIssuer name when cert-manager TLS is selected."""
    ingress = config.get("ingress")
    if ingress is None:
        if scheme == "http":
            return ""
        raise CommandError("product_fullspec.json must define ingress")
    if not isinstance(ingress, dict):
        raise CommandError("product_fullspec.json must define ingress as an object")

    tls = ingress.get("tls", [])
    if not isinstance(tls, list) or not all(isinstance(item, str) for item in tls):
        raise CommandError("product_fullspec.json must define ingress.tls as a list")
    if "cert_manager" not in tls:
        return ""

    cert_manager = ingress.get("cert_manager")
    if not isinstance(cert_manager, dict):
        raise CommandError(
            "product_fullspec.json must define ingress.cert_manager when "
            "ingress.tls selects cert_manager"
        )
    cluster_issuer = cert_manager.get("ClusterIssuer")
    if not isinstance(cluster_issuer, str) or not cluster_issuer:
        raise CommandError(
            "product_fullspec.json must define ingress.cert_manager.ClusterIssuer "
            "when ingress.tls selects cert_manager"
        )
    return cluster_issuer
