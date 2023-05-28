local k = import "k.libsonnet";

{
    local namespace = k.core.v1.namespace,
    local deployment = k.apps.v1.deployment,
    local container = k.core.v1.container,
    local pod = k.core.v1.pod,
    local port = k.core.v1.containerPort,
    local volumeMount = k.core.v1.volumeMount,
    local volume = k.core.v1.volume,
    local service = k.core.v1.service,


    local stelar_ns = $._config.stelar_ns,

    stelar_namespace: namespace.new(stelar_ns),

    local _minio_pod = {
        local m=pod.metadata,
        local s=pod.spec,
        thepod: pod.new("minio") 
        + m.withNamespace(stelar_ns)
        + m.withLabels({
            app: 'minio',
        })
        + s.withContainers([
            container.new(
                name="minio",
                image="quay.io/minio/minio:latest"
            ) 
            + container.withCommand(['/bin/bash','-c'])
            + container.withArgs(['minio server /data --console-address :9090'])
            + container.withVolumeMounts([
                volumeMount.new(
                    name='localvolume',
                    mountPath='/data',
                    readOnly=false)
            ])
        ])
        //+ s.withNodeSelector(nodeSelector)
        + s.withVolumes([
            volume.fromHostPath(
                name="localvolume",
                hostPath="/mnt/disk1/data",
            ) + {
                hostPath+: {
                    type: "DirectoryOrCreate"
                }
            }
            //k.core.v1.hostPathVolumeSource.withType(type="DirectoryOrCreate"),
        ])
        ,
    },

    minio_pod: _minio_pod.thepod,
}
