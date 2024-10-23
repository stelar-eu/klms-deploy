local tk_env = import 'spec.json';

local urllib = import "urllib.libsonnet";
local t = import 'transform.libsonnet';
local IMAGE_CONFIG = import 'images.jsonnet';
local PORTS = import 'stdports.libsonnet';

{
  _tk_env:: tk_env.spec,

  _config+:: {
    namespace: tk_env.spec.namespace,
    dynamicStorageClass: 'ebs-sc',
  },

  access:: {
    // Root Domain Name to the host of the STELAR deployment
    endpoint: {
      scheme: 'https',
      host: 'stelar.gr',
      port: null,
    },

    // certificates, passwords etc
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
      ROOT_DOMAIN: "stelar.gr",
      PRIMARY_SUBDOMAIN: "klms", # klms.stelar.gr
      KEYCLOAK_SUBDOMAIN: "kc", # kc.stelar.gr
      MINIO_API_SUBDOMAIN: "minio", # minio.stelar.gr
    }
  },

  provisioning:: {
    namespace: $._config.namespace,
    dynamic_volume_storage_class: 'ebs-sc',
  },


  ##########################################
  ## The Platform Specific Model ###########
  ##########################################
  # This structure contains parameters     #
  # that WILL change when deploying the    #
  # cluster among  different platforms.    #
  ##########################################
  psm::
    self.access {
      endpoint+: { 
        url: urllib.url_from(self),
      }
    } 
    + self.provisioning
    + {
        images: IMAGE_CONFIG {
          API_IMAGE: 'petroud/stelar-tuc:data-api-prod',
          CKAN_IMAGE: 'petroud/stelar-tuc:ckan',
        },
    } 
    + {
        cluster: self.cluster
      },


  ##########################################
  ## The Platform Independent Model ########
  ##########################################
  # This structure contains parameters     #
  # that wont change when deploying the    #
  # cluster among different platforms.     #
  ##########################################
  pim:: {
    ports: PORTS, //TCP ports for all services. See stdports.libsonnet for more
  },


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
      passing the PIM and PSM as arguments. This
      will generate the manifests for all services 
      of the cluster. PIM and PSM are commonly passed
      between the service manifests to achieve 
      integrity and universality for the parameters.
  */
  manifests: t.transform_pim_psm($.pim, $.psm, $.components)

}
