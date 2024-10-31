
local k = import "k.libsonnet";
local pvol = import "pvolumes.libsonnet";
local svcs = import "services.libsonnet";

local container = k.core.v1.container;
local stateful = k.apps.v1.statefulSet;
local containerPort = k.core.v1.containerPort;
local volumeMount = k.core.v1.volumeMount;
local vol = k.core.v1.volume;
local cmap = k.core.v1.configMap;
local envSource = k.core.v1.envVarSource;

// local MINIOCONFIG = import 'minioconfig.jsonnet';
// local IMAGE_CONFIG = import 'images.jsonnet';
// local PORT = import "stdports.libsonnet";

local MINIO_CONFIG(pim, config) = {
    MINIO_ROOT_USER : pim.minio.MINIO_ROOT_USER,# 'root'
    //MINIO_ROOT_PASSWORD: psm.minio.MINIO_ROOT_PASSWORD,# "stelartuc"
    MINIO_BROWSER_REDIRECT: pim.minio.MINIO_BROWSER_REDIRECT,# "true"
    MINIO_BROWSER_REDIRECT_URL: config.cluster.endpoint.SCHEME+'://'+config.cluster.endpoint.PRIMARY_SUBDOMAIN+'.'+config.cluster.endpoint.ROOT_DOMAIN+'/s3',# "https://klms.stelar.gr/s3"
    MINIO_IDENTITY_OPENID_REDIRECT_URI: config.cluster.endpoint.SCHEME+'://'+config.cluster.endpoint.PRIMARY_SUBDOMAIN+'.'+config.cluster.endpoint.ROOT_DOMAIN+'/s3',# "https://klms.stelar.gr/s3"
};


{
    manifest(pim, config):  {

        minio_cmap: cmap.new("minio-cmap") + 
                    cmap.withData(MINIO_CONFIG(pim, config)),

        pvc_minio_storage: pvol.pvcWithDynamicStorage(
            "minio-storage",
            "2Gi",
            pim.dynamic_volume_storage_class,),
        

        minio_deployment: stateful.new(name="minio", containers=[
            // container.new("minio",IMAGE_CONFIG.MINIO_IMAGE)
            container.new("minio",pim.images.MINIO_IMAGE)
           + container.withImagePullPolicy("Always")
           + container.withEnvFrom([{
                    configMapRef: {
                        name: "minio-cmap",
                    },
                }])
           + container.withEnvMap({
                MINIO_ROOT_PASSWORD: envSource.secretKeyRef.withName(config.secrets.minio.minio_root_password_secret).withKey("password"),
           })
           + container.withPorts([
                containerPort.newNamed(pim.ports.MINIO, "minio"),
                containerPort.newNamed(pim.ports.MINIOAPI, "minapi")
           ])
           + container.withCommand(['minio','server','/data','--console-address',':'+pim.ports.MINIO])
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
