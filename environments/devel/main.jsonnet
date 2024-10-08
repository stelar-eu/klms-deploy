local tk_env = import 'spec.json';

local urllib = import "urllib.libsonnet";
local t = import 'transform.libsonnet';


{
  _tk_env:: tk_env.spec,

  _config+:: {
    namespace: tk_env.spec.namespace,

    dynamicStorageClass: 'longhorn',
  },

  access:: {
    // External access to the STELAR core deployment
    endpoint: {
      scheme: 'https',
      host: 'devel.vsamtuc.top',
      port: null,
    },

    // certificates, passwords etc
  },

  provisioning:: {
    namespace: $._config.namespace,
    dynamic_volume_storage_class: 'longhorn',
  },

  psm::
    self.access {
      endpoint+: { url: urllib.url_from(self) }
    }
    +
    self.provisioning,

  components:: [
    import 'db.libsonnet',
    import 'ckan.libsonnet',
    import 'stelarapi.libsonnet',
    import 'ontop.libsonnet',
    import 'superset.libsonnet',
    import 'stelar_ingress.libsonnet',
  ],


  /*
      Translate to manifests
  */

  //thepsm: self.psm,

  manifests: t.transform_psm($.psm, $.components)
}
