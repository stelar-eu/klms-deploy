/*
    CKAN deployment and configuration as STELAR data catalog.

    This file is a Kubernetes adaptation of the docker_compose file
    of the ckan distribution

*/
local k = import "k.libsonnet";
//local util = import "github.com/grafana/jsonnet-libs/ksonnet-util/util.libsonnet";
local urllib = "urllib.libsonnet";

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

local psqlURI = "postgresql://%(user)s:%(password)s@%(host)s/%(db)s";


/*****************************

    Environment/configuration values
    
 */


local DBENV = import "dbenv.jsonnet";


# These should be initialized randomly
# However, it is possible to let the ckan setup code to do it.
# Note: if we do it here, the values override the ones in ckan.ini (from setup)
local SESSION_SECRETS = {
    #
    # CKAN___BEAKER__SESSION__SECRET: 'string:2UXr0cQqC3ryE',
    # CKAN___API_TOKEN__JWT__ENCODE__SECRET: 'string:I5VCpxaM20tbV0okIfaYpqiVXF',
    # CKAN___API_TOKEN__JWT__DECODE__SECRET: 'string:I5VCpxaM20tbV0okIfaYpqiVXF',
};



local KEYCLOAK_CONFIG(psm) = {
    //local ckan_endpoint = urllib.url_from(psm.endpoint+{ path: "/dc" }),
    local ckan_endp = psm.endpoint { path: '/dc' },
    local ckan_endp_url1 =  "%(scheme)s://%(host)s%(path)s" %  ckan_endp,
    local ckan_endp_url2 = urllib.url_from(ckan_endp),

    CKANEXT__KEYCLOAK__SERVER_URL: "https://authst.vsamtuc.top/",
    CKANEXT__KEYCLOAK__CLIENT_ID: "dummy_client",
    CKANEXT__KEYCLOAK__REALM_NAME:  "stelarstaging2",
    CKANEXT__KEYCLOAK__REDIRECT_URI:  ckan_endp_url1,
    CKANEXT__KEYCLOAK__CLIENT_SECRET_KEY:  "fooofootos",
    CKANEXT__KEYCLOAK__BUTTON_STYLE:  "",
    CKANEXT__KEYCLOAK__ENABLE_CKAN_INTERNAL_LOGIN: "True",
};


local ENV = 
    DBENV 
    + SESSION_SECRETS 
    + {
    # CKAN core
    CKAN_VERSION: '2.10.0',
    CKAN_PORT: "5000",
    CKAN_PORT_HOST: "5000",
    CKAN_SITE_URL: "<from psm>",
    CKAN__ROOT_PATH: "/dc",
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

    CKANEXT__SPATIAL__COMMON_MAP__TYPE: "OpenStreetMap.Mapnik",

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

    CKAN_REDIS_URL: "redis://redis:6379/1",
    TEST_CKAN_REDIS_URL: "redis://redis:6379/1",
};


local PORT = import "stdports.libsonnet";


// These images are used unchanged
local SOLR_IMAGE_NAME = "ckan/ckan-solr:%s" % ENV.SOLR_IMAGE_VERSION;
local DATAPUSHER_IMAGE_NAME = "ckan/ckan-base-datapusher:%s" % ENV.DATAPUSHER_VERSION;

// The following image has been customized
local CKAN_IMAGE_NAME = 'vsam/stelar-okeanos:ckan';



/*********************

    The CKAN deployment.

    It requires
    (a) a custom image,
    (b) a volume for storing various data
    (c) the deployment itself

 */


local pvc_ckan_storage(psm) = pvol.pvcWithLonghornStorage("ckan-storage", "5Gi");

local ckan_deployment(psm) = 
    local MYENV = ENV {
        CKAN_SITE_URL: psm.endpoint.url
    }
    + KEYCLOAK_CONFIG(psm)
    ;
    stateful.new(
    name="ckan",
    containers = [
        container.new('ckan', CKAN_IMAGE_NAME)
        + container.withImagePullPolicy("Always")
        + container.withEnvMap(MYENV)
        
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
            containerPort.newNamed(PORT.CKAN, "api"),
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



local pvc_solr_data(psm) = pvol.pvcWithLonghornStorage("solr-data", "5Gi");

local solr_deployment(psm) = stateful.new(
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

local datapusher_deployment(psm) = deploy.new(
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







/*************************************

    Final assembly of all resources

 */



{

    /*
        local obfuscate(m)=std.mapWithKey(function(k,d) std.base64(std.manifestJsonMinified(d)), m),

        configs: [
            cm.new("ckan-dbenv", DBENV),
            secret.new("ckan-session-secrets",{})
            + secret.withData(obfuscate(SESSION_SECRETS))
        ],
    */


    manifest(psm): {
        ckan: [
            pvc_ckan_storage(psm),
            ckan_deployment(psm),
            svcs.headlessService.new("ckan", "ckan", PORT.CKAN, "api")
        ],


        solr: [
            pvc_solr_data(psm), 
            solr_deployment(psm),
            svcs.headlessService.new("solr", "solr", PORT.SOLR, "solr")
        ],

        local datapusher_dep = datapusher_deployment(psm),
        datapusher: [
            datapusher_dep,
            svcs.serviceFor(datapusher_dep)
        ],

    }
}

