
local k = import "k.libsonnet";

{
    local deployment = k.apps.v1.deployment,
    local container = k.core.v1.container,
    local pod = k.core.v1.pod,
    local port = k.core.v1.containerPort,
    local volumeMount = k.core.v1.volumeMount,
    local volume = k.core.v1.volume,
    local service = k.core.v1.service,

    local volume_spec_data = pod.spec.withVolumes([
            volume.fromHostPath(
                name="localvolume",
                hostPath="/data/localvolume",
            ) + {
                hostPath+: {
                    type: "DirectoryOrCreate"
                }
            }
        ]),


    /*
        This is a minimal install of minio with a hard-coded provision
        for a data directory.
     */

    new(): 
        pod.new("minio") 
        + pod.metadata.withLabels({
            app: 'minio',
        })
        + pod.spec.withContainers([
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
        //+ pod.spec.withNodeSelector(nodeSelector)
        + volume_spec_data
        ,

}
