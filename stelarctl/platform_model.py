"""Pydantic schema for the STELAR platform model YAML."""

from pydantic import BaseModel, model_validator
from typing import Literal, Optional


class DNSConfig(BaseModel):
    """DNS root, scheme, and service subdomain prefixes."""

    root: str
    scheme: Literal["http", "https"]
    keycloak: str = "kc"
    minio: str = "minio"
    primary: str = "klms"
    registry: str = "img"

    def url_for(self, name: str) -> str:
        """Build the service URL for one configured subdomain field."""
        prefix = getattr(self, name)
        return f"{self.scheme}://{prefix}.{self.root}"


class AppConfig(BaseModel):
    """Application-level settings injected into generated manifests."""

    smtp_server: str
    smtp_port: str
    smtp_username: str
    s3_console_url: str
    enable_llm_search: bool = False
    groq_api_url: Optional[str] = None
    groq_api_model: Optional[str] = None

    @model_validator(mode="after")
    def groq_fields_required_when_llm_enabled(self):
        """Require Groq settings when optional LLM search is enabled."""
        if self.enable_llm_search:
            if not self.groq_api_url:
                raise ValueError("groq_api_url is required when enable_llm_search is true")
            if not self.groq_api_model:
                raise ValueError("groq_api_model is required when enable_llm_search is true")
        return self


class SecretData(BaseModel):
    """Supported data keys for model-defined Kubernetes secrets."""

    password: Optional[str] = None
    key: Optional[str] = None


class Secret(BaseModel):
    """Named Kubernetes Secret with password or key data."""

    name: str
    data: SecretData


class StorageConfig(BaseModel):
    """StorageClass names used by generated persistent volumes."""

    dynamic_class: str       # used for PVCs (databases, minio, solr)
    provisioning_class: str  # used for provisioning volumes


class TLSConfig(BaseModel):
    """TLS mode and optional cert-manager issuer."""

    mode: Literal["cert-manager", "manual", "none"]
    issuer: Optional[str] = None

    @model_validator(mode="after")
    def issuer_required_for_cert_manager(self):
        """Require an issuer only for cert-manager-managed TLS."""
        if self.mode == "cert-manager" and not self.issuer:
            raise ValueError("issuer is required when mode is cert-manager")
        return self


class InfrastructureConfig(BaseModel):
    """Cluster infrastructure prerequisites referenced by generated manifests."""

    storage: StorageConfig
    ingress_class: str
    tls: TLSConfig


class PlatformModel(BaseModel):
    """Complete desired-state input accepted by `stelarctl` commands."""

    platform: str
    k8s_context: str
    namespace: str
    author: str
    tier: Literal["core", "full"]
    infrastructure: InfrastructureConfig
    dns: DNSConfig
    config: AppConfig
    secrets: list[Secret]

    @model_validator(mode="after")
    def tls_mode_compatible_with_scheme(self):
        """Prevent TLS configuration when generated URLs use plain HTTP."""
        if self.dns.scheme == "http" and self.infrastructure.tls.mode != "none":
            raise ValueError("tls.mode must be 'none' when scheme is http")
        return self
