
local tk_env = import 'spec.json';
local urllib = import "urllib.libsonnet";
local t = import 'transform.libsonnet';
local defaults = import 'pim.libsonnet';
local secrets = import 'secrets.libsonnet';

{
  _tk_env:: tk_env.spec,
  _config+:: {
    namespace: tk_env.spec.namespace,
    dynamicStorageClass: 'ebs-sc',
  },
  provisioning:: {
    namespace: $._config.namespace,
    dynamic_volume_storage_class: 'ebs-sc',
  },
  access:: {
    // Root Domain Name to the host of the STELAR deployment
    endpoint: {
      scheme: 'https',
      host: 'stelar.gr',
      port: null,
    },
  },
  cluster:: {
    endpoint: {
      /*
      In order for the cluster to be able to operate,
      (3) subdomains (belonging to ROOT_DOMAIN) are needed:
      - PRIMARY:  It is the subdomain at which
                  the main reverse proxy listens.
                  Services as the Data API, Console,
                  MinIO Console, OnTop, DC are covered
                  by this.
      - KEYCLOAK: Keycloak SSO server needs a dedicated
                  domain in order to serve SSO to services.
                  We choose here to use subdomain which
                  will work just fine.
      - MINIO_API: In order to avoid conflicts with MinIO
                  paths (confusing a MinIO path for a
                  reverse proxy path) we choose to use
                  separate subdomain for the MinIO API only
                  (Note: MinIO CONSOLE is served by the
                  PRIMARY subdomain. )
      */
      SCHEME: "https",
      ROOT_DOMAIN: "stelar.gr",
      PRIMARY_SUBDOMAIN: "klms",
      KEYCLOAK_SUBDOMAIN: "kc",
      MINIO_API_SUBDOMAIN: "minio",
    }
  },
  configuration::
    self.cluster
    + {
      api: {
        SMTP_SERVER: "stelar.gr",
        SMTP_PORT: "465",
        SMTP_USERNAME: "info@stelar.gr",
        S3_CONSOLE_URL: "https://klms.stelar.gr/s3/login",
      }
    }
    + {
      minio:{
        API_DOMAIN: 'https://minio.stelar.gr',
        CONSOLE_DOMAIN: "https://klms.stelar.gr/s3",
      }
    }
    + {
      secrets: {
        db: {
          postgres_db_password_secret: "postgresdb-secret",
          ckan_db_password_secret: "ckandb-secret",
          keycloak_db_passowrd_secret: "keycloakdb-secret",
          datastore_db_password_secret: "datastoredb-secret",
        },
        keycloak: {
          root_password_secret: "keycloakroot-secret",
        },
        api: {
          smtp_password_secret: "smtpapi-secret",
        },
        ckan: {
          ckan_admin_password_secret: "ckanadmin-secret",
        },
        minio: {
          minio_root_password_secret: "minioroot-secret",
        }
      }
    },
  ##########################################
  ## The Platform Independent Model ########
  ##########################################
  pim::
    self.provisioning
    + {
        images: {
          API_IMAGE: 'petroud/stelar-tuc:data-api-dev',
          CKAN_IMAGE: 'petroud/stelar-tuc:ckan',
          POSTGIS_IMAGE:"petroud/stelar-tuc:postgres",
          MINIO_IMAGE:"quay.io/minio/minio:latest",
          ONTOP_IMAGE: "petroud/stelar-tuc:ontop",
          KEYCLOAK_IMAGE:"quay.io/keycloak/keycloak:25.0",
          REDIS_IMAGE:"redis:7",
          KC_INIT:"petroud/stelar-tuc:kcinit"
        },
    }
    + defaults,

  /*
  Here the library for each component is
  defined in order to use them for manifest
  generation later on. The services included
  here will be actively deployed in the K8s
  cluster.
  */
  components:: [
    import 'db.libsonnet',
    import 'redis.libsonnet',
    import 'ontop.libsonnet',
    import 'minio.libsonnet',
    import 'keycloak.libsonnet',
    import 'stelarapi.libsonnet',
    import 'stelar_ingress.libsonnet',
    import 'ckan.libsonnet',
    import 'systeminit.libsonnet'
  ],
  /*
  Translate to manifests. This will call the
  manifest function of each component above,
  passing the PIM and Config as arguments. This
  will generate the manifests for all services
  of the cluster.
  */
  manifests: t.transform_pim($.pim, $.configuration, $.components)
}
