"""Generate the `main.jsonnet` entry point for a Tanka environment."""

import textwrap
from pathlib import Path

try:
    from .platform_model import PlatformModel
except ImportError:
    from platform_model import PlatformModel


def _cluster_issuer(model: PlatformModel) -> str:
    """Return the Jsonnet literal for the configured cert-manager issuer."""
    if model.infrastructure.tls.mode == "cert-manager":
        # Jsonnet needs a quoted string for real issuer names, but `null` for
        # manual or disabled TLS so downstream libraries can branch cleanly.
        return f"'{model.infrastructure.tls.issuer}'"
    return "null"


def _insecure_minio(model: PlatformModel) -> str:
    """Return the MinIO client TLS flag expected by existing Jsonnet libraries."""
    # Existing Jsonnet consumes this value as the string "true"/"false", not as
    # a boolean. Keep that contract to avoid changing generated manifests.
    return "false" if model.infrastructure.tls.mode != "none" else "true"


def _secret_name(model: PlatformModel, name: str) -> str:
    """Resolve a required logical secret name from the platform model."""
    match = next((s for s in model.secrets if s.name == name), None)
    if match is None:
        # Fail while generating main.jsonnet rather than allowing Tanka to fail
        # later with a less direct missing-field error.
        raise ValueError(f"Secret '{name}' not found in platform model")
    return match.name


def generate_main_jsonnet(model: PlatformModel) -> str:
    """Render `main.jsonnet` for the supplied validated platform model."""
    dns = model.dns
    config = model.config
    infra = model.infrastructure

    minio_url = dns.url_for("minio")
    primary_url = dns.url_for("primary")
    issuer = _cluster_issuer(model)
    insecure_minio = _insecure_minio(model)

    llm_enable = "true" if config.enable_llm_search else "false"
    groq_url = config.groq_api_url or "null"
    groq_model = config.groq_api_model or "null"

    # The generated Jsonnet keeps the platform model as the single operator input
    # while still delegating Kubernetes-object construction to the existing
    # libsonnet stack. Each top-level section below feeds an established library:
    #   - _tk_env and _config mirror Tanka environment metadata.
    #   - provisioning carries storage choices into persistent-volume helpers.
    #   - cluster/configuration provide endpoint, API, MinIO, LLM, and secret
    #     names consumed by component libraries.
    #   - pim and components select images and workload definitions for the tier.
    return textwrap.dedent(f"""\
        local tk_env = import 'spec.json';
        local t = import 'transform.libsonnet';
        local pim = import 'pim.libsonnet';
        local tier = import 'tiers/{model.tier}.libsonnet';

        {{
          _tk_env:: tk_env.spec,
          _config+:: {{
            namespace: tk_env.spec.namespace,
            dynamicStorageClass: '{infra.storage.dynamic_class}',
          }},
          provisioning:: {{
            namespace: $._config.namespace,
            dynamic_volume_storage_class: '{infra.storage.provisioning_class}',
          }},
          cluster:: {{
            endpoint: {{
              SCHEME: '{dns.scheme}',
              ROOT_DOMAIN: '{dns.root}',
              CLUSTER_ISSUER: {issuer},
              PRIMARY_SUBDOMAIN: '{dns.primary}',
              KEYCLOAK_SUBDOMAIN: '{dns.keycloak}',
              MINIO_API_SUBDOMAIN: '{dns.minio}',
              REGISTRY_SUBDOMAIN: '{dns.registry}',
            }}
          }},
          configuration::
            self.cluster
            + {{
              api: {{
                SMTP_SERVER: '{config.smtp_server}',
                SMTP_PORT: '{config.smtp_port}',
                SMTP_USERNAME: '{config.smtp_username}',
                S3_CONSOLE_URL: '{config.s3_console_url}',
              }}
            }}
            + {{
              minio: {{
                API_DOMAIN: '{minio_url}',
                CONSOLE_DOMAIN: '{primary_url}/s3',
                INSECURE_MC_CLIENT: '{insecure_minio}',
              }}
            }}
            + {{
              llm_search: {{
                ENABLE_LLM_SEARCH: '{llm_enable}',
                GROQ_API_URL: '{groq_url}',
                GROQ_MODEL: '{groq_model}',
              }}
            }}
            + {{
              secrets: {{
                db: {{
                  postgres_db_password_secret: '{_secret_name(model, "postgresdb-secret")}',
                  ckan_db_password_secret: '{_secret_name(model, "ckandb-secret")}',
                  keycloak_db_passowrd_secret: '{_secret_name(model, "keycloakdb-secret")}',
                  datastore_db_password_secret: '{_secret_name(model, "datastoredb-secret")}',
                  quay_db_password_secret: '{_secret_name(model, "quaydb-secret")}',
                }},
                keycloak: {{
                  root_password_secret: '{_secret_name(model, "keycloakroot-secret")}',
                }},
                api: {{
                  smtp_password_secret: '{_secret_name(model, "smtpapi-secret")}',
                  session_secret_key: '{_secret_name(model, "session-secret-key")}',
                }},
                ckan: {{
                  ckan_admin_password_secret: '{_secret_name(model, "ckanadmin-secret")}',
                  ckan_auth_secret: 'ckan-auth-secret',
                }},
                minio: {{
                  minio_root_password_secret: '{_secret_name(model, "minioroot-secret")}',
                }}
              }}
            }},
          pim::
            self.provisioning
            + pim.with_images(tier.images),

          components:: tier.components
            + (if $.configuration.llm_search.ENABLE_LLM_SEARCH == 'true' then [import 'llmsearch.libsonnet'] else []),
          manifests: t.transform_pim($.pim, $.configuration, $.components)
        }}
    """)


def write_main_jsonnet(model: PlatformModel, env_path: str) -> Path:
    """Write generated Jsonnet into the requested environment directory."""
    path = Path(env_path) / "main.jsonnet"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(generate_main_jsonnet(model))
    print(f"✅ main.jsonnet written to {path}")
    return path
