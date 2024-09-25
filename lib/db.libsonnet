/*
    Code to deploy the STELAR core database component

 */
local k = import "k.libsonnet";

local podinit = import "podinit.libsonnet";
local pvol = import "pvolumes.libsonnet";
local svcs = import "services.libsonnet";


/* K8S API MODEL */
local deploy = k.apps.v1.deployment;
local stateful = k.apps.v1.statefulSet;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;
local servicePort = k.core.v1.servicePort;
local volumeMount = k.core.v1.volumeMount;
local pod = k.core.v1.pod;
local vol = k.core.v1.volume;
local service = k.core.v1.service;
local cm = k.core.v1.configMap;
local secret = k.core.v1.secret;

local DBENV = import "dbenv.jsonnet";
local PORT = import "stdports.libsonnet";
local IMAGE_CONFIG = import "images.jsonnet";

/**********************************

    POSTGIS is required. 

    A custom image also contains the schema of the tool execution metadata.

 */

{

    manifest(psm): {

        pvc_db_storage: pvol.pvcWithDynamicStorage(
            "postgis-storage", 
            "5Gi", 
            psm.dynamic_volume_storage_class),

        postgis_deployment: stateful.new(name="db", containers=[
            container.new("postgis", IMAGE_CONFIG.POSTGIS_IMAGE_NAME)
            + container.withImagePullPolicy("Always")

            + container.withEnvMap(DBENV)
            + container.withEnvMap({
                /* We are using /var/lib/postgresql/data as mountpoint, and initdb does not like it,
                so we just use a subdirectory...
                */
                PGDATA: "/var/lib/postgresql/data/pgdata",
            })

            // Expose port 
            + container.withPorts([
                containerPort.newNamed(PORT.PG, "psql")      
                ])

            // liveness check
            //+ container.livenessProbe.exec.withCommand("pg_isready")
            + container.livenessProbe.exec.withCommand([
                "pg_isready", "-U", "postgres"
            ])
            + container.livenessProbe.withInitialDelaySeconds(30)
            + container.livenessProbe.withPeriodSeconds(10)

            + container.withVolumeMounts([
                volumeMount.new("postgis-storage-vol", "/var/lib/postgresql/data", false)
            ])
        ],
        podLabels={
            'app.kubernetes.io/name': 'data-catalog',
            'app.kubernetes.io/component': 'postgis',
        })
        + stateful.spec.template.spec.withVolumes([
            vol.fromPersistentVolumeClaim("postgis-storage-vol", "postgis-storage")
        ]),

        postgis_svc: svcs.headlessService.new("db", "postgis", PORT.PG)
        
    }


}