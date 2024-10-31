/*
    Deployment of the STELAR core database component as statefulset
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
local envVar = k.core.v1.envVar;
local envSource = k.core.v1.envVarSource;


local DB_CONFIG(pim) = {

    ########################################
    ##  DEFAULT DATABASE & SERVER ##########
    ########################################  
    POSTGRES_USER: pim.db.POSTGRES_USER, # 'postgres'
    #POSTGRES_PASSWORD: config.db.POSTGRES_USER_PASSWORD, # 'postgres'
    POSTGRES_DB: pim.db.POSTGRES_DEFAULT_DB, # 'postgres'
    POSTGRES_HOST: pim.db.POSTGRES_HOST,
    POSTGRES_PORT: std.toString(pim.ports.PG),


    ########################################
    ##  STELAR DATABASE W/ LOT OF SCHEMAS  #
    ########################################  
    CKAN_DB_USER: pim.db.CKAN_DB_USER, # 'ckan'
    #CKAN_DB_PASSWORD: config.db.CKAN_DB_PASSWORD, # 'ckan'
    CKAN_DB: pim.db.STELAR_DB, #'stelar'


    ########################################
    ##  KEYCLOAK SCHEMA AND USER ###########
    ########################################  
    KEYCLOAK_DB_USER: pim.db.KEYCLOAK_DB_USER, # 'keycloak'
    #KEYCLOAK_DB_PASSWORD: config.db.KEYCLOAK_DB_PASSWORD, # 'keycloak'
    KEYCLOAK_DB: pim.db.STELAR_DB, # 'stelar'
    KEYCLOAK_DB_SCHEMA: pim.db.KEYCLOAK_DB_SCHEMA, # 'keycloak'


    //CKAN modules schemata and databases ??????????? what about this
    DATASTORE_READONLY_USER: 'datastore_ro',
    DATASTORE_READONLY_PASSWORD: 'datastore',
    DATASTORE_DB: 'datastore',
};


{

    manifest(pim, config): {

        pvc_db_storage: pvol.pvcWithDynamicStorage(
            "postgis-storage", 
            "5Gi", 
            pim.dynamic_volume_storage_class),

        postgis_deployment: stateful.new(name="db", containers=[
            container.new("postgis", pim.images.POSTGIS_IMAGE)
            + container.withImagePullPolicy("Always")

            + container.withEnvMap(DB_CONFIG(pim))
            + container.withEnvMap({
                /* We are using /var/lib/postgresql/data as mountpoint, and initdb does not like it,
                so we just use a subdirectory...
                */
                PGDATA: "/var/lib/postgresql/data/pgdata",
            })
            // Pass secrets to the container by referencing their names
            + container.withEnvMap({
                CKAN_DB_PASSWORD: envSource.secretKeyRef.withName(config.secrets.ckan_db_password_secret).withKey("password"),          
                POSTGRES_DB_PASSWORD: envSource.secretKeyRef.withName(config.secrets.postgres_db_password_secret).withKey("password"),          
                KEYCLOAK_DB_PASSWORD: envSource.secretKeyRef.withName(config.keycloak_db_passowrd_secret).withKey("password"),
            })
            // Expose port 
            + container.withPorts([
                containerPort.newNamed(pim.ports.PG, "psql")      
            ])

            // liveness check
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

        postgis_svc: svcs.headlessService.new("db", "postgis", pim.ports.PG)
        
    }

}