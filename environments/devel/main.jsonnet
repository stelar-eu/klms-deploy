local tk_env = import 'spec.json';

local t = import 'transform.libsonnet';


{
  _tk_env:: tk_env.spec,

  _config+:: {
    namespace: tk_env.spec.namespace,

    dynamicStorageClass: 'longhorn',
  },

  access:: {
    // External access to the STELAR core deployment
    hostname: 'devel.vsamtuc.top',
    port: null,
    protocol: 'https',

    // certificates, passwords etc
  },

  provisioning:: {
    namespace: $._config.namespace,
    dynamic_volume_storage_class: 'longhorn',
  },

  psm::
    self.access {
      access_url: '%(protocol)s://%(hostname)s%(portspec)s/' % ($.access {
                                                                  portspec: if super.port == null then '' else ':' + super.port,
                                                                }),


    }
    +
    self.provisioning,

  components:: [
    import 'db.libsonnet',
    import 'ckan.libsonnet',
    import 'stelarapi.libsonnet',
    import 'ontop.libsonnet',
  ],


  /*
      Translate to manifests
  */

  thepsm: self.psm,

  //manifests:
  //    t.transform_psm($.psm, $.components)
}
