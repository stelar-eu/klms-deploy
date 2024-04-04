/*
    CKAN deployment and configuration as STELAR data catalog.

    This file is a Kubernetes adaptation of the docker_compose file
    of the ckan distribution

*/
local k = import "k.libsonnet";
local util = import "github.com/grafana/jsonnet-libs/ksonnet-util/util.libsonnet";
local podinit = import "podinit.libsonnet";

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
local cm = k.core.v1.configMap;
local secret = k.core.v1.secret;

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


/**
    Used to create headless services
 */
local headlessService = {

    /*
        Return a manifest for a headless Service.

        Headless services are 

        name(str): the name of the resource
        component(str): annotation value for 'app.kubernetes.io/component' to select on
        port(int): the port of the service
        portName(str, optional): the name of the port
     */
    new(name, component, port, portName=null):: service.new(name, {
            'app.kubernetes.io/component': component
        },
        [
            if portName != null then
                servicePort.newNamed(portName, port, port)
            else
                servicePort.new(port, port)
        ]
    )
    + service.spec.withClusterIP("None")
};



local psqlURI = "postgresql://%(user)s:%(password)s@%(host)s/%(db)s";



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


# These should be initialized randomly
# However, it is possible to let the ckan setup code to do it.
# Note: if we do it here, the values override the ones in ckan.ini (from setup)
local SESSION_SECRETS = {
    #
    # CKAN___BEAKER__SESSION__SECRET: 'string:2UXr0cQqC3ryE',
    # CKAN___API_TOKEN__JWT__ENCODE__SECRET: 'string:I5VCpxaM20tbV0okIfaYpqiVXF',
    # CKAN___API_TOKEN__JWT__DECODE__SECRET: 'string:I5VCpxaM20tbV0okIfaYpqiVXF',
};



local KEYCLOAK_CONFIG = {
    CKANEXT__KEYCLOAK__SERVER_URL: "https://authst.vsamtuc.top/",
    CKANEXT__KEYCLOAK__CLIENT_ID: "dummy_client",
    CKANEXT__KEYCLOAK__REALM_NAME:  "stelarstaging2",
    CKANEXT__KEYCLOAK__REDIRECT_URI:  "https://stelar.vsamtuc.top/",
    CKANEXT__KEYCLOAK__CLIENT_SECRET_KEY:  "fooofootos",
    CKANEXT__KEYCLOAK__BUTTON_STYLE:  "",
    CKANEXT__KEYCLOAK__ENABLE_CKAN_INTERNAL_LOGIN: "True",
};


local ENV = DBENV 
    + SESSION_SECRETS 
    + KEYCLOAK_CONFIG
    + {
    # CKAN core
    CKAN_VERSION: '2.10.0',
    CKAN_PORT: "5000",
    CKAN_PORT_HOST: "5000",
    //CKAN_SITE_URL: "http://ckan:5000/",
    CKAN_SITE_URL: "https://stelar.vsamtuc.top/",
    CKAN_SITE_ID: "default",


    # TODO: Move these in a secret!
    CKAN_SYSADMIN_NAME: "ckan_admin",
    CKAN_SYSADMIN_PASSWORD: "stelar1234",
    CKAN_SYSADMIN_EMAIL: "vsam@softnet.tuc.gr",

    local _DB_HOST = {host: DBENV.POSTGRES_HOST},
    local _CKAN_U = _DB_HOST+{user: DBENV.CKAN_DB_USER, password: DBENV.CKAN_DB_PASSWORD},
    local _DS_U = _DB_HOST+{user: DBENV.DATASTORE_READONLY_USER, password: DBENV.DATASTORE_READONLY_PASSWORD},


    CKAN_SQLALCHEMY_URL: psqlURI % (_CKAN_U + {db: DBENV.CKAN_DB}),
    CKAN_DATASTORE_WRITE_URL: psqlURI % (_CKAN_U + {db: DBENV.DATASTORE_DB}),
    CKAN_DATASTORE_READ_URL: psqlURI  % (_DS_U + {db: DBENV.DATASTORE_DB}),

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

    CKAN__PLUGINS: "envvars image_view text_view recline_view datastore datapusher"
      +" keycloak"
      +" resource_proxy geo_view"
      +" spatial_metadata spatial_query"
      ,
    CKAN__HARVEST__MQ__TYPE: "redis",
    CKAN__HARVEST__MQ__HOSTNAME: "redis",
    CKAN__HARVEST__MQ__PORT: "6379",
    CKAN__HARVEST__MQ__REDIS_DB: "1",

    # timezone!
    TZ: "UTC",

    DATAPUSHER_VERSION: "0.0.20",
    CKAN_DATAPUSHER_URL: "http://datapusher:8800",
    CKAN__DATAPUSHER__CALLBACK_URL_BASE: "http://ckan:5000",
    DATAPUSHER_REWRITE_RESOURCES: "True",
    DATAPUSHER_REWRITE_URL: "http://ckan:5000",

    SOLR_IMAGE_VERSION: "2.10-solr9-spatial",
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
    PG: 5432,
};


// These images are used unchanged
local SOLR_IMAGE_NAME = "ckan/ckan-solr:%s" % ENV.SOLR_IMAGE_VERSION;
local REDIS_IMAGE_NAME = "redis:%s" % ENV.REDIS_VERSION;
local DATAPUSHER_IMAGE_NAME = "ckan/ckan-base-datapusher:%s" % ENV.DATAPUSHER_VERSION;

// The following two images have been customized
local POSTGIS_IMAGE_NAME = 'vsam/stelar-okeanos:postgis';
local CKAN_IMAGE_NAME = 'vsam/stelar-okeanos:ckan';



/**********************************

    POSTGIS is required. 

    A custom image also contains the schema of the tool execution metadata.

 */


local pvc_db_storage = pvcWithLonghornStorage("postgis-storage", "5Gi");

local postgis_deployment = stateful.new(name="db", containers=[
        container.new("postgis", POSTGIS_IMAGE_NAME)
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
    ])
;


/*********************

    The CKAN deployment.

    It requires
    (a) a custom image,
    (b) a volume for storing various data
    (c) the deployment itself

 */


local pvc_ckan_storage = pvcWithLonghornStorage("ckan-storage", "5Gi");

local ckan_deployment = stateful.new(
    name="ckan",
    containers = [
        container.new('ckan', CKAN_IMAGE_NAME)
        + container.withImagePullPolicy("Always")
        + container.withEnvMap(ENV)
        
        + (
        container.livenessProbe.exec.withCommand(
            ["/usr/bin/curl", "--fail", "http://localhost:%s/api/3/action/status_show" % ENV.CKAN_PORT_HOST]
            )
        + container.livenessProbe.withInitialDelaySeconds(30)
        + container.livenessProbe.withPeriodSeconds(60)
        + container.livenessProbe.withTimeoutSeconds(5)
        + container.livenessProbe.withFailureThreshold(5)
        )

        // Expose 5000
        + container.withPorts([
            containerPort.newNamed(5000, "api"),
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
+ stateful.spec.template.spec.withInitContainers([
    podinit.wait4_redis("wait4-redis", ENV.CKAN_REDIS_URL),
    podinit.wait4_postgresql("wait4-db", ENV.CKAN_SQLALCHEMY_URL + "?sslmode=disable"),
    podinit.wait4_http("wait4-solr", "http://solr:8983/solr/"),
])
+ stateful.spec.template.spec.withVolumes([
    vol.fromPersistentVolumeClaim("ckan-storage-vol", "ckan-storage")
])
+ stateful.spec.template.spec.securityContext.withRunAsUser(92)
+ stateful.spec.template.spec.securityContext.withRunAsGroup(92)
+ stateful.spec.template.spec.securityContext.withFsGroup(92)
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

        + container.livenessProbe.exec.withCommand(
            ["/usr/bin/wget", "-qO", "/dev/null", "http://127.0.0.1:8983/solr/"]
            )
        + container.livenessProbe.withInitialDelaySeconds(120)
        + container.livenessProbe.withPeriodSeconds(20)
        + container.livenessProbe.withFailureThreshold(3)
        + container.livenessProbe.withTimeoutSeconds(45)

        //+ container.readinessProbe.httpGet.withPort(8983)
        //+ container.readinessProbe.httpGet.withPath("/solr/")
        + container.readinessProbe.exec.withCommand(
            ["/usr/bin/curl", "http://127.0.0.1:8983/solr/"]
            )

        + container.readinessProbe.withInitialDelaySeconds(120)
        + container.readinessProbe.withPeriodSeconds(20)
        + container.readinessProbe.withTimeoutSeconds(45)
        + container.readinessProbe.withFailureThreshold(5)
        + container.readinessProbe.withSuccessThreshold(1)

        // Expose 8983
        + container.withPorts([
            containerPort.newNamed(PORT.SOLR, "solr"),
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



/*********************
    The DATAPUSHER deployment.

    It requires
    (c) the deployment itself
 */

local datapusher_deployment = deploy.new(
    name="datapusher",
    containers = [
        container.new('datapusher', DATAPUSHER_IMAGE_NAME)
        //+ container.withEnvMap(ENV)

        + container.livenessProbe.exec.withCommand(
            ["/usr/bin/wget", "-qO", "/dev/null", "http://127.0.0.1:8800"]
            )
        + container.livenessProbe.withInitialDelaySeconds(30)
        + container.livenessProbe.withPeriodSeconds(15)
        + container.livenessProbe.withTimeoutSeconds(10)
        + container.livenessProbe.withFailureThreshold(5)

        + container.readinessProbe.httpGet.withPort(8800)
        + container.readinessProbe.withInitialDelaySeconds(15)
        + container.readinessProbe.withPeriodSeconds(15)
        + container.readinessProbe.withTimeoutSeconds(10)
        + container.readinessProbe.withFailureThreshold(5)
        + container.readinessProbe.withSuccessThreshold(1)


        // Expose 
        + container.withPorts([
            containerPort.newNamed(PORT.DATAPUSHER, "datapusher"),
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
        //+ container.withEnvMap(ENV)

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
            containerPort.newNamed(PORT.REDIS, "redis"),
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

    local obfuscate(m)=std.mapWithKey(function(k,d) std.base64(std.manifestJsonMinified(d)), m),

    configs: [
        cm.new("ckan-dbenv", DBENV),
        secret.new("ckan-session-secrets",{})
        + secret.withData(obfuscate(SESSION_SECRETS))
    ],

    ckan: [
        pvc_ckan_storage,
        ckan_deployment,
        headlessService.new("ckan", "ckan", PORT.CKAN, "api")
    ],

    db: [
        pvc_db_storage,
        postgis_deployment,
        headlessService.new("db", "postgis", PORT.PG)
    ],

    solr: [
        pvc_solr_data, 
        solr_deployment,
        headlessService.new("solr", "solr", PORT.SOLR, "solr")
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
            "cert-manager.io/cluster-issuer": "letsencrypt-production",
            "nginx.ingress.kubernetes.io/proxy-connect-timeout": "60s",
            "nginx.ingress.kubernetes.io/ssl-redirect": "true"
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

        + ing.spec.withTls([
            k.networking.v1.ingressTLS.withHosts("stelar.vsamtuc.top")
            + k.networking.v1.ingressTLS.withSecretName("ckan-ui-tls")
        ])
        ,

    ontop: import "ontop.libsonnet"
}

