local k = import "k.libsonnet";
local pg = import "postgresql.libsonnet";
local minio = import "minio.libsonnet";
local airflow = import "airflow.libsonnet";

{
    local storage = k.storage.v1,
    local sc = storage.storageClass,

    _config:: {
        stelar_ns: 'stelar-default',

        scls_host_data: sc.new("host_data") 
            + sc.withProvisioner('k8s.io/minikube-hostpath')
            /* BROKEN
            + sc.withParameters({
                hostPath: {
                    path: "/data"
                }
            })
            */
            + sc.withReclaimPolicy('Retain')
            + sc.withVolumeBindingMode('Immediate'),
    },

    local namespace = k.core.v1.namespace,
    local stelar_ns = $._config.stelar_ns,
    local storageclass_hostpath_data = $._config.scls_host_data,

    // stelar_namespace: namespace.new(stelar_ns),

    // Deploy postgresql
    //local pg1 = pg.new(stelar_ns),
    //postgres: pg.setStorageRequest(pg1, '2Gi'),

    // BROKEN
    // sc_host_data: storageclass_hostpath_data,

    // Deploy minio
    //minio_pod: minio.new(),

    // Deploy airflow
    // airflow: airflow.new(stelar_ns),
}
