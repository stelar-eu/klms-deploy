
local k = import "k.libsonnet";
local pvol = import "pvolumes.libsonnet";
local svcs = import "services.libsonnet";

local deployment = k.apps.v1.deployment;
local container = k.core.v1.container;
local stateful = k.apps.v1.statefulSet;
local containerPort = k.core.v1.containerPort;
local pod = k.core.v1.pod;
local port = k.core.v1.containerPort;
local volumeMount = k.core.v1.volumeMount;
local vol = k.core.v1.volume;
local cmap = k.core.v1.configMap;
local service = k.core.v1.service;

local MINIOCONFIG = import 'minioconfig.jsonnet';
local IMAGE_CONFIG = import 'images.jsonnet';
local PORT = import "stdports.libsonnet";


{
    manifest(psm):  {

        minio_cmap: cmap.new("minio-cmap") + 
                    cmap.withData(MINIOCONFIG.ENV),

        pvc_minio_storage: pvol.pvcWithDynamicStorage(
            "minio-storage",
            "2Gi",
            psm.dynamic_volume_storage_class,),
        

        minio_deployment: stateful.new(name="minio", containers=[
            container.new("minio",IMAGE_CONFIG.MINIO_IMAGE)
           + container.withImagePullPolicy("Always")
           + container.withEnvFrom([{
                    configMapRef: {
                        name: "minio-cmap",
                    },
                }])
           + container.withPorts([
                containerPort.newNamed(PORT.MINIO, "minio"),
                containerPort.newNamed(PORT.MINIOAPI, "minapi")
           ])
           + container.withCommand(['minio','server','/data','--console-address',':9001'])
           + container.withVolumeMounts([
                volumeMount.new("minio-storage-vol","/data",false)
           ])
        ],
        podLabels={
            'app.kubernetes.io/name': 'object-storage',
            'app.kubernetes.io/component': 'minio',
        })
        + stateful.spec.template.spec.withVolumes([
            vol.fromPersistentVolumeClaim("minio-storage-vol","minio-storage")
        ]),

        minio_svc: svcs.serviceFor(self.minio_deployment),
    }
}
