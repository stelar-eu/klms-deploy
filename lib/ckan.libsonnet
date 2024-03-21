/*
    CKAN deployment and configuration as STELAR data catalog.

    This file is a Kubernetes adaptation of the docker_compose file
    of the ckan distribution

*/
local k = import "k.libsonnet";
local util = import "github.com/grafana/jsonnet-libs/ksonnet-util/util.libsonnet";

local deploy = k.apps.v1.deployment;
local stateful = k.apps.v1.statefulSet;
local pvc = k.core.v1.persistentVolumeClaim;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;
local servicePort = k.core.v1.servicePort;
local volumeMount = k.core.v1.volumeMount;
local pod = k.core.v1.pod;
local vol = k.core.v1.volume;
local service = k.core.v1.service;

/**
    Used to create persistent volume claims

 */
local pvcWithLonghornStorage(name, gibytes)=
    pvc.new(name)
    + pvc.spec.withStorageClassName("longhorn")
    + pvc.spec.withAccessModes(['ReadWriteOnce'])
    + pvc.spec.withVolumeMode('Filesystem')
    + pvc.spec.resources.withRequests({
        storage: gibytes
    })
;



local psqlURI(user, password, host, db) = 
   "postgresql://%(user)s:%(password)s@%(host)s/%(db)s" % {
        user: user, 
        password: password, 
        host: host, 
        db: db
   };



/*****************************

    Environment/configuration values
    
 */


local DBENV = {
    # CKAN databases
    POSTGRES_USER: "postgres",
    POSTGRES_PASSWORD: "postgres",
    POSTGRES_DB: "postgres",
    POSTGRES_HOST: "db",
    POSTGRES_PORT: "5432",

    CKAN_DB_USER: "ckan",
    CKAN_DB_PASSWORD: "ckan",
    CKAN_DB: "ckan",

    DATASTORE_READONLY_USER: "datastore_ro",
    DATASTORE_READONLY_PASSWORD: "datastore",
    DATASTORE_DB: "datastore"
    
};


local ENV = DBENV {
    # CKAN core
    CKAN_VERSION: '2.10.0',
    CKAN_PORT: "5000",
    CKAN_PORT_HOST: "5000",
    CKAN_SITE_URL: "http://ckan:5000/",
    CKAN_SITE_ID: "default",

    # These should be initialized randomly
    CKAN___BEAKER__SESSION__SECRET: 'string:2UXr0cQqC3ryE',
    CKAN___API_TOKEN__JWT__ENCODE__SECRET: 'string:0okIfaYpqiVXF',
    CKAN___API_TOKEN__JWT__DECODE__SECRET: 'string:I5VCpxaM20tbV',

    # TODO: Move these in a secret!
    CKAN_SYSADMIN_NAME: "ckan_admin",
    CKAN_SYSADMIN_PASSWORD: "stelar1234",
    CKAN_SYSADMIN_EMAIL: "your_email@example.com",
    
    CKAN_SQLALCHEMY_URL: psqlURI(
        DBENV.CKAN_DB_USER, 
        DBENV.CKAN_DB_PASSWORD, 
        DBENV.POSTGRES_HOST,
        DBENV.CKAN_DB
    ),

    CKAN_DATASTORE_WRITE_URL: psqlURI(
        DBENV.CKAN_DB_USER, 
        DBENV.CKAN_DB_PASSWORD, 
        DBENV.POSTGRES_HOST,
        DBENV.DATASTORE_DB
    ),

    CKAN_DATASTORE_READ_URL: psqlURI(
        DBENV.DATASTORE_READONLY_USER, 
        DBENV.DATASTORE_READONLY_PASSWORD,
        DBENV.POSTGRES_HOST,
        DBENV.DATASTORE_DB
    ),

    # Test database connections
    TEST_CKAN_SQLALCHEMY_URL: self.CKAN_SQLALCHEMY_URL+"_test",
    TEST_CKAN_DATASTORE_WRITE_URL: self.CKAN_DATASTORE_WRITE_URL+"_test",
    TEST_CKAN_DATASTORE_READ_URL: self.CKAN_DATASTORE_READ_URL+"_test",

    # Must match the volumeMount below
    CKAN_STORAGE_PATH: "/var/lib/ckan",
    
    # TODO: These need configuration
    'CKAN_SMTP_SERVER': "smtp.corporateict.domain:25",
    'CKAN_SMTP_STARTTLS': "True",
    'CKAN_SMTP_USER': "user",
    'CKAN_SMTP_PASSWORD': "pass",
    'CKAN_SMTP_MAIL_FROM': "ckan@localhost",

    CKAN__PLUGINS: "envvars image_view text_view recline_view datastore datapusher",
    # KLMS also requires these CKAN plugins: "resource_proxy geo_view spatial_metadata spatial_query keycloak"
    'CKAN__HARVEST__MQ__TYPE': "redis",
    'CKAN__HARVEST__MQ__HOSTNAME': "redis",
    'CKAN__HARVEST__MQ__PORT': "6379",
    'CKAN__HARVEST__MQ__REDIS_DB': "1",

    # timezone!
    TZ: "UTC",

    DATAPUSHER_VERSION: "0.0.20",
    CKAN_DATAPUSHER_URL: "http://datapusher:8800",
    CKAN__DATAPUSHER__CALLBACK_URL_BASE: "http://ckan:5000",
    DATAPUSHER_REWRITE_RESOURCES: "True",
    DATAPUSHER_REWRITE_URL: "http://ckan:5000",

    SOLR_IMAGE_VERSION: "2.10-solr9",
    CKAN_SOLR_URL: "http://solr:8983/solr/ckan",
    TEST_CKAN_SOLR_URL: "http://solr:8983/solr/ckan",

    REDIS_VERSION: "6",
    CKAN_REDIS_URL: "redis://redis:6379/1",
    TEST_CKAN_REDIS_URL: "redis://redis:6379/1",
};


// Used to collect hard-coded ports above.
// TODO: actually, make links consistent with this map.
local PORT = {
    CKAN: 5000,
    REDIS: 6379,
    SOLR: 8983,
    DATAPUSHER: 8800,
};



local SOLR_IMAGE_NAME = "ckan/ckan-solr:%s" % ENV.SOLR_IMAGE_VERSION;
local POSTGIS_IMAGE_NAME = 'vsam/stelar-okeanos:postgis';
local CKAN_IMAGE_NAME = 'vsam/stelar-okeanos:ckan';
local REDIS_IMAGE_NAME = "redis:%s" % ENV.REDIS_VERSION;
local DATAPUSHER_IMAGE_NAME = "ckan/ckan-base-datapusher:%s" % ENV.DATAPUSHER_VERSION;



/**********************************

    POSTGIS is required. 

    A custom image also contains the schema of the tool execution metadata.

 */


local pvc_db_storage = pvcWithLonghornStorage("postgis-storage", "5Gi");

local postgis_deployment = stateful.new(name="db", containers=[
        container.new("postgis", POSTGIS_IMAGE_NAME)
        + container.withEnvMap(DBENV)

        + container.withEnvMap({
            /* We are using /var/lib/postgresql/data as mountpoint, and initdb does not like it,
            so we just use a subdirectory...
            */
            PGDATA: "/var/lib/postgresql/data/pgdata",
        })

        // Expose 5432
        + container.withPorts([
            k.core.v1.containerPort.newNamed(5432, "psql")      
            ])

        // liveness check
        + container.livenessProbe.exec.withCommand("pg_isready")
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
    ])
;

local postgis_svc = service.new("db", {
        'app.kubernetes.io/component': "postgis"
    },
    [
        servicePort.new(5432, 5432)
    ]
 )
    + service.spec.withClusterIP("None")
;


/*********************

    The CKAN deployment.

    It requires
    (a) a custom image,
    (b) a volume for storing various data
    (c) the deployment itself

 */



local env_config_map = k.core.v1.configMap.new(
    "ckan_config_map",
    "Silly data"
);

local pvc_ckan_storage = pvcWithLonghornStorage("ckan-storage", "5Gi");

local ckan_deployment = stateful.new(
    name="ckan",
    containers = [
        container.new('ckan', CKAN_IMAGE_NAME)
        + container.withImagePullPolicy("Always")
        + container.withEnvMap(ENV)

        /*
        + container.livenessProbe.exec.withCommand(
            ["/usr/bin/wget", "-qO", "/dev/null", "http://localhost:%s" % ENV.CKAN_PORT_HOST]
            )
        + container.livenessProbe.withInitialDelaySeconds(30)
        + container.livenessProbe.withPeriodSeconds(20)
        */

        // Expose 5000
        + container.withPorts([
            k.core.v1.containerPort.newNamed(5000, "api"),
        ])

        + container.withVolumeMounts([
            volumeMount.new("ckan-storage-vol", ENV.CKAN_STORAGE_PATH, false)
            ])

        + container.securityContext.withAllowPrivilegeEscalation(false)

    ],
    podLabels = {
        'app.kubernetes.io/name': 'data-catalog',
        'app.kubernetes.io/component': 'ckan',
    }
)
+ stateful.spec.template.spec.withVolumes([
    vol.fromPersistentVolumeClaim("ckan-storage-vol", "ckan-storage")
])
+ stateful.spec.template.spec.securityContext.withRunAsUser(92)
+ stateful.spec.template.spec.securityContext.withRunAsGroup(92)
+ stateful.spec.template.spec.securityContext.withFsGroup(92)
;

local ckan_service = 
    service.new("ckan", {
            'app.kubernetes.io/component': "ckan"
        },
        [
            servicePort.newNamed("api", 5000, 5000),
        ]
    )
        + service.spec.withClusterIP("None")    
;



/*********************
    The SOLR deployment.

    It requires
    (b) a volume for storing various data
    (c) the deployment itself
 */



local pvc_solr_data = pvcWithLonghornStorage("solr-data", "5Gi");

local solr_deployment = stateful.new(
   name="solr",
    containers = [
        container.new('solr', SOLR_IMAGE_NAME)
        + container.withEnvMap(ENV)

        /*
        + container.livenessProbe.exec.withCommand(
            ["/usr/bin/wget", "-qO", "/dev/null", "http://127.0.0.1:8983/solr/"]
            )
        + container.livenessProbe.withInitialDelaySeconds(30)
        + container.livenessProbe.withPeriodSeconds(20)

        + container.readinessProbe.httpGet.withPort(8983)
        + container.readinessProbe.httpGet.withPath("/solr/")
        + container.readinessProbe.withInitialDelaySeconds(50)
        + container.readinessProbe.withPeriodSeconds(10)
        //+ container.readinessProbe.withTimeoutSeconds(2)
        + container.readinessProbe.withFailureThreshold(3)
        + container.readinessProbe.withSuccessThreshold(1)
        */

        // Expose 8983
        + container.withPorts([
            k.core.v1.containerPort.newNamed(PORT.SOLR, "solr"),
        ])

        + container.withVolumeMounts([
            volumeMount.new("solr-storage-vol", "/var/solr", false)
            ])

        + container.securityContext.withAllowPrivilegeEscalation(false)
    ],
    podLabels = {
        'app.kubernetes.io/name': 'data-catalog',
        'app.kubernetes.io/component': 'solr',
    }
)
+ stateful.spec.template.spec.withVolumes([
    vol.fromPersistentVolumeClaim("solr-storage-vol", "solr-data")
])
+ stateful.spec.template.spec.securityContext.withFsGroup(8983)
;

local solr_service = 
    service.new("solr", {
            'app.kubernetes.io/component': "solr"
        },
        [
            servicePort.newNamed("solr", PORT.SOLR, PORT.SOLR),
        ]
    )
        + service.spec.withClusterIP("None")    
;



/*********************
    The DATAPUSHER deployment.

    It requires
    (c) the deployment itself
 */

local datapusher_deployment = deploy.new(
   name="datapusher",
    containers = [
        container.new('datapusher', DATAPUSHER_IMAGE_NAME)
        + container.withEnvMap(ENV)

        + container.livenessProbe.exec.withCommand(
            ["/usr/bin/wget", "-qO", "/dev/null", "http://127.0.0.1:8800"]
            )
        + container.livenessProbe.withInitialDelaySeconds(30)
        + container.livenessProbe.withPeriodSeconds(5)
        + container.livenessProbe.withFailureThreshold(12)

        + container.readinessProbe.httpGet.withPort(8800)
        + container.readinessProbe.withInitialDelaySeconds(50)
        + container.readinessProbe.withPeriodSeconds(10)
        + container.readinessProbe.withTimeoutSeconds(2)
        + container.readinessProbe.withFailureThreshold(3)
        + container.readinessProbe.withSuccessThreshold(1)


        // Expose 
        + container.withPorts([
            k.core.v1.containerPort.newNamed(PORT.DATAPUSHER, "datapusher"),
        ])

    ],
    podLabels = {
        'app.kubernetes.io/name': 'data-catalog',
        'app.kubernetes.io/component': 'datapusher',
    }
)
;




/*********************
    The REDIS deployment.

    It requires
    (c) the deployment itself
 */

local redis_deployment = deploy.new(
   name="redis",
    containers = [
        container.new('redis', REDIS_IMAGE_NAME)
        + container.withEnvMap(ENV)

        + container.livenessProbe.exec.withCommand(
            ["/usr/local/bin/redis-cli", "-e", "QUIT"]
            )
        + container.livenessProbe.withInitialDelaySeconds(30)
        + container.livenessProbe.withPeriodSeconds(10)

        + container.readinessProbe.exec.withCommand(
            ["/usr/local/bin/redis-cli", "-e", "QUIT"]
            )
        + container.readinessProbe.withInitialDelaySeconds(30)
        + container.readinessProbe.withPeriodSeconds(10)

        // Expose 
        + container.withPorts([
            k.core.v1.containerPort.newNamed(PORT.REDIS, "redis"),
        ])

    ],
    podLabels = {
        'app.kubernetes.io/name': 'data-catalog',
        'app.kubernetes.io/component': 'redis',
    }
)
;




/*************************************

    Final assembly of all resources

 */




{
    ckan: [
        pvc_ckan_storage,
        ckan_deployment,
        ckan_service
    ],

    db: [
        pvc_db_storage,
        postgis_deployment,
        postgis_svc
    ],

    solr: [
        pvc_solr_data, 
        solr_deployment,
        solr_service
    ],

    datapusher: [
        datapusher_deployment,
        util.serviceFor(datapusher_deployment)
    ],

    redis: [
        redis_deployment,
        util.serviceFor(redis_deployment)
    ],


    /****************************
        Ingress for the data catalog

     */

    local ing = k.networking.v1.ingress,
    local ingrule = k.networking.v1.ingressRule,
    local ingpath = k.networking.v1.httpIngressPath,

    ingress: ing.new("data-catalog")
        + ing.metadata.withAnnotations({
            'foo': 'bar'
        })
        + ing.spec.withIngressClassName("nginx")
        + ing.spec.withRules([
            ingrule.withHost("stelar.vsamtuc.top")
            + ingrule.http.withPaths([
                ingpath.withPath("/")
                + ingpath.withPathType("Prefix")
                + ingpath.backend.service.withName("ckan")
                + ingpath.backend.service.port.withName("api")
            ])
        ])
        ,


}


