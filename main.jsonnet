local tk_env = import 'spec.json';
local t = import 'transform.libsonnet';
local pim = import 'pim.libsonnet';
local tier = import 'tiers/core.libsonnet';

{
  _tk_env:: tk_env.spec,
  _config+:: {
    namespace: tk_env.spec.namespace,
    dynamicStorageClass: 'longhorn',
  },
  provisioning:: {
    namespace: $._config.namespace,
    dynamic_volume_storage_class: 'longhorn',
  },
  cluster:: {
    endpoint: {
      SCHEME: 'https',
      ROOT_DOMAIN: 'vsamtuc.top',
      CLUSTER_ISSUER: 'letsencrypt-production',
      PRIMARY_SUBDOMAIN: 'klms',
      KEYCLOAK_SUBDOMAIN: 'kc',
      MINIO_API_SUBDOMAIN: 'minio',
      REGISTRY_SUBDOMAIN: 'img',
    }
  },
  configuration::
    self.cluster
    + {
      api: {
        SMTP_SERVER: 'smtp.sendgrid.net',
        SMTP_PORT: '587',
        SMTP_USERNAME: 'apikey',
        S3_CONSOLE_URL: 'https://klms.vsamtuc.top/s3/login',
      }
    }
    + {
      minio: {
        API_DOMAIN: 'https://minio.vsamtuc.top',
        CONSOLE_DOMAIN: 'https://klms.vsamtuc.top/s3',
        INSECURE_MC_CLIENT: 'false',
      }
    }
    + {
      llm_search: {
        ENABLE_LLM_SEARCH: 'false',
        GROQ_API_URL: 'null',
        GROQ_MODEL: 'null',
      }
    }
    + {
      secrets: {
        db: {
          postgres_db_password_secret: 'postgresdb-secret',
          ckan_db_password_secret: 'ckandb-secret',
          keycloak_db_passowrd_secret: 'keycloakdb-secret',
          datastore_db_password_secret: 'datastoredb-secret',
          quay_db_password_secret: 'quaydb-secret',
        },
        keycloak: {
          root_password_secret: 'keycloakroot-secret',
        },
        api: {
          smtp_password_secret: 'smtpapi-secret',
          session_secret_key: 'session-secret-key',
        },
        ckan: {
          ckan_admin_password_secret: 'ckanadmin-secret',
          ckan_auth_secret: 'ckan-auth-secret',
        },
        minio: {
          minio_root_password_secret: 'minioroot-secret',
        },
        llm_search: {
          groq_api_key_secret: 'null',
        }
      }
    },
  pim::
    self.provisioning
    + pim.with_images(tier.images),

  components:: tier.components
    + (if $.configuration.llm_search.ENABLE_LLM_SEARCH == 'true' then [import 'llmsearch.libsonnet'] else []),
  manifests: t.transform_pim($.pim, $.configuration, $.components)
}
