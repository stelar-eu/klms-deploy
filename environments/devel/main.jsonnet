local tk_env = import "spec.json";


{
    _tk_env:: tk_env.spec,

    _config+:: {
        namespace: tk_env.spec.namespace,

        dynamicStorageClass: "longhorn"
    },    

    deploy_model:: {
        stelar_hostname: "devel.vsamtuc.top"
    },

    platform_model:: {
        dynamic_volume_storage_class: "longhorn"
    },

    manifests: import "ckan.libsonnet",
}

