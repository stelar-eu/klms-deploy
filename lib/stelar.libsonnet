local k = import "k.libsonnet";
local pg = import "postgresql.libsonnet";

// (import "airflow.libsonnet") +
// (import "minio.libsonnet") + 

pg + {
    _config:: {
        stelar_ns: 'stelar-default'
    },

    local namespace = k.core.v1.namespace,
    local stelar_ns = $._config.stelar_ns,

    stelar_namespace: namespace.new(stelar_ns),

}
