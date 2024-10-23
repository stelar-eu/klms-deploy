
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

// local MINIOCONFIG = import 'minioconfig.jsonnet';
// local IMAGE_CONFIG = import 'images.jsonnet';
// local PORT = import "stdports.libsonnet";

local MINIO_CONFIG(pim,psm) = {
    MINIO_ROOT_USER : pim.minio.MINIO_ROOT_USER,# 'root'
    MINIO_ROOT_PASSWORD: psm.minio.MINIO_ROOT_PASSWORD,# "stelartuc"
    MINIO_BROWSER_REDIRECT: pim.minio.MINIO_BROWSER_REDIRECT,# "true"
    MINIO_BROWSER_REDIRECT_URL: 'https://'+psm.cluster.endpoint.PRIMARY_SUBDOMAIN+'.'+psm.cluster.endpoint.ROOT_DOMAIN+'/s3',# "https://klms.stelar.gr/s3"
    MINIO_IDENTITY_OPENID_REDIRECT_URI: 'https://'+psm.cluster.endpoint.PRIMARY_SUBDOMAIN+'.'+psm.cluster.endpoint.ROOT_DOMAIN+'/s3',# "https://klms.stelar.gr/s3"
};


{
    manifest(pim,psm):  {

        minio_cmap: cmap.new("minio-cmap") + 
                    cmap.withData(MINIO_CONFIG(pim,psm)),

        pvc_minio_storage: pvol.pvcWithDynamicStorage(
            "minio-storage",
            "2Gi",
            psm.dynamic_volume_storage_class,),
        

        minio_deployment: stateful.new(name="minio", containers=[
            // container.new("minio",IMAGE_CONFIG.MINIO_IMAGE)
            container.new("minio",psm.images.MINIO_IMAGE)
           + container.withImagePullPolicy("Always")
           + container.withEnvFrom([{
                    configMapRef: {
                        name: "minio-cmap",
                    },
                }])
           + container.withPorts([
                // containerPort.newNamed(PORT.MINIO, "minio"),
                // containerPort.newNamed(PORT.MINIOAPI, "minapi")
                containerPort.newNamed(pim.ports.MINIO, "minio"),
                containerPort.newNamed(pim.ports.MINIOAPI, "minapi")
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
