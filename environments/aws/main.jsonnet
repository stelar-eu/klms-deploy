local tk_env = import 'spec.json';
local urllib = import "urllib.libsonnet";
local t = import 'transform.libsonnet';
local defaults = import 'pim.libsonnet';

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

  cluster::{
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
                    seperate subdomain for the MinIO API only
                    (Note: MinIO CONSOLE is served by the
                    PRIMARY subdomain. )
      */
      SCHEME: "https",
      ROOT_DOMAIN: "stelar.gr",
      PRIMARY_SUBDOMAIN: "klms", # klms.stelar.gr
      KEYCLOAK_SUBDOMAIN: "kc", # kc.stelar.gr
      MINIO_API_SUBDOMAIN: "minio", # minio.stelar.gr
    }
  },



  configuration::
    {
      cluster: self.cluster,
    }
    + {
      api: {
        SMTP_SERVER: "",
        SMTP_PORT: "",
        SMTP_USERNAME: "",
      }
    }
    + { 
      secrets:{
        db: {
          postgres_db_password_secret: "secret-name",
          ckan_db_password_secret: "secret-name",
          keycloak_db_passowrd_secret: "secret-name",
          datastore_db_password_secret: "secret-name",
        },
        keycloak: {
          root_password_secret: "secret-name",
        },
        api: {
          smtp_password_secret: "secret-name",
        },
        ckan: {
          ckan_admin_password_secret: "secret-name",
        },
        minio: {
          minio_root_passowrd_secret: "secret-name",
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
          API_IMAGE: 'petroud/stelar-tuc:data-api-prod',
          CKAN_IMAGE: 'petroud/stelar-tuc:ckan',
          POSTGIS_IMAGE:"petroud/stelar-tuc:postgres",
          MINIO_IMAGE:"quay.io/minio/minio:latest",
          ONTOP_IMAGE: "vsam/stelar-okeanos:ontop",
          KEYCLOAK_IMAGE:"quay.io/keycloak/keycloak:latest",
          REDIS_IMAGE:"redis:7",
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
    import 'ckan.libsonnet',
    import 'stelarapi.libsonnet',
    import 'ontop.libsonnet',
    import 'minio.libsonnet',
    import 'keycloak.libsonnet',
    import 'stelar_ingress.libsonnet',
  ],


  /*
      Translate to manifests. This will call the 
      manifest function of each component above,
      passing the PIM and Config as arguments. This
      will generate the manifests for all services 
      of the cluster. PIM and config are commonly passed
      between the service manifests to achieve 
      integrity and universality for all parameters.
  */
  manifests: t.transform_pim($.pim, $.configuration, $.components)

}
