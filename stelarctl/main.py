from pydantic import BaseModel, model_validator
from typing import Literal, Optional


class DNSConfig(BaseModel):
    root: str
    scheme: Literal["http", "https"]
    keycloak: str = "kc"
    minio: str = "minio"
    primary: str = "klms"
    registry: str = "img"

    def url_for(self, name: str) -> str:
        prefix = getattr(self, name)
        return f"{self.scheme}://{prefix}.{self.root}"


class AppConfig(BaseModel):
    smtp_server: str
    smtp_port: str
    smtp_username: str
    s3_console_url: str
    enable_llm_search: bool = False
    groq_api_url: Optional[str] = None
    groq_api_model: Optional[str] = None

    @model_validator(mode="after")
    def groq_fields_required_when_llm_enabled(self):
        if self.enable_llm_search:
            if not self.groq_api_url:
                raise ValueError("groq_api_url is required when enable_llm_search is true")
            if not self.groq_api_model:
                raise ValueError("groq_api_model is required when enable_llm_search is true")
        return self


class SecretData(BaseModel):
    password: Optional[str] = None
    key: Optional[str] = None


class Secret(BaseModel):
    name: str
    data: SecretData


class StorageConfig(BaseModel):
    dynamic_class: str       # used for PVCs (databases, minio, solr)
    provisioning_class: str  # used for provisioning volumes


class TLSConfig(BaseModel):
    mode: Literal["cert-manager", "manual", "none"]
    issuer: Optional[str] = None

    @model_validator(mode="after")
    def issuer_required_for_cert_manager(self):
        if self.mode == "cert-manager" and not self.issuer:
            raise ValueError("issuer is required when mode is cert-manager")
        return self


class InfrastructureConfig(BaseModel):
    storage: StorageConfig
    ingress_class: str
    tls: TLSConfig


class PlatformModel(BaseModel):
    platform: str
    k8s_context: str
    namespace: str
    author: str
    infrastructure: InfrastructureConfig
    dns: DNSConfig
    config: AppConfig
    secrets: list[Secret]

    @model_validator(mode="after")
    def tls_mode_compatible_with_scheme(self):
        if self.dns.scheme == "http" and self.infrastructure.tls.mode != "none":
            raise ValueError("tls.mode must be 'none' when scheme is http")
        return self


def load_platform_model(path: str) -> PlatformModel:
    import yaml
    from pydantic import ValidationError

    with open(path) as f:
        raw = yaml.safe_load(f)

    try:
        return PlatformModel(**raw)
    except ValidationError as e:
        print(e)
        raise SystemExit(1)


def main():
    model = load_platform_model("stelarctl/example_models/okeanos.yaml")
    print(model)


if __name__ == "__main__":
    main()
