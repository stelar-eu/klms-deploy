local tk_env = import 'spec.json';

local urllib = import "urllib.libsonnet";
local t = import 'transform.libsonnet';
local IMAGE_CONFIG = import 'images.jsonnet';

{
  _tk_env:: tk_env.spec,

  _config+:: {
    namespace: tk_env.spec.namespace,

    dynamicStorageClass: 'ebs-sc',
  },

  access:: {
    // External access to the STELAR core deployment
    endpoint: {
      scheme: 'https',
      host: 'stelar.gr',
      port: null,
    },

    // certificates, passwords etc
  },

  provisioning:: {
    namespace: $._config.namespace,
    dynamic_volume_storage_class: 'ebs-sc',
  },

  psm::
    self.access {
      endpoint+: { url: urllib.url_from(self) }
    }
    +
    self.provisioning
    + {
        images: IMAGE_CONFIG {
          API_IMAGE: 'petroud/stelar-tuc:data-api-prod',
          CKAN_IMAGE: 'petroud/stelar-tuc:ckan',
        },
      } ,

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
      Translate to manifests
  */

  //thepsm: self.psm,

  manifests: t.transform_psm($.psm, $.components)
}
