/*
    CKAN deployment and configuration as STELAR data catalog.

    This file is a Kubernetes adaptation of the docker_compose file
    of the ckan distribution

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
local volumeMount = k.core.v1.volumeMount;
local vol = k.core.v1.volume;

local envSource = k.core.v1.envVarSource;

/*****************************

    Environment/configuration values
    
*/

local KEYCLOAK_CONFIG(pim,config) = {
    CKANEXT__KEYCLOAK__SERVER_URL: config.endpoint.SCHEME+"://"+config.endpoint.KEYCLOAK_SUBDOMAIN+'.'+config.endpoint.ROOT_DOMAIN, 
    CKANEXT__KEYCLOAK__CLIENT_ID: pim.keycloak.KC_CKAN_CLIENT_NAME,
    CKANEXT__KEYCLOAK__REALM_NAME:  pim.keycloak.REALM, 
    CKANEXT__KEYCLOAK__REDIRECT_URI:  config.endpoint.SCHEME+"://"+config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN + "/dc/user/sso_login",
    CKANEXT__KEYCLOAK__BUTTON_STYLE:  "",
    CKANEXT__KEYCLOAK__ENABLE_CKAN_INTERNAL_LOGIN: "True",
};


local ENV= {
    # CKAN core
    CKAN_VERSION: '2.10.0',
    CKAN_PORT: "5000",
    CKAN_PORT_HOST: "5000",
    CKAN__ROOT_PATH: "/dc",
    CKAN_SITE_ID: "default",

    CKAN_SYSADMIN_NAME: "admin",
    CKAN_SYSADMIN_EMAIL: "info@stelar.gr",

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

    
    # Using settings for the standard OSM tile server
    CKANEXT__SPATIAL__COMMON_MAP__TYPE: "custom",
    CKANEXT__SPATIAL__COMMON_MAP__CUSTOM__URL: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    CKANEXT__SPATIAL__COMMON_MAP__ATTRIBUTION: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',

    # There is also the option to use the standard OSM subdomains, to speed up map
    # retrieval, but I need to check as to how they are used. Theoretically,
    # I also need to use the {s} substitution in the URL above. But in fact,
    # there are three subdomains, 'a' 'b' and 'c'. I am not sure about the
    # correct format of this environment variable!
    # CKANEXT__SPATIAL__COMMON_MAP__SUBDOMAINS: "abc"

    # timezone!
    TZ: "UTC",

    ##### TO-DO: Should this below be fetched from PIM??????????????????????????????????????????????
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


/*********************

    The CKAN deployment.

    It requires
    (a) a custom image,
    (b) the deployment itself

 */

local ckan_deployment(pim, config) =
  deploy.new(
    name = "ckan",
    replicas = 1,
    containers = [
        container.new('ckan', pim.images.CKAN_IMAGE)
        + container.withImagePullPolicy("Always")
        + container.withEnvMap(ENV +
                               KEYCLOAK_CONFIG(pim, config) + {
            CKAN_SITE_URL: config.endpoint.SCHEME+"://"+config.endpoint.PRIMARY_SUBDOMAIN+"."+config.endpoint.ROOT_DOMAIN,
            CKAN_SYSADMIN_PASSWORD: envSource.secretKeyRef.withName(config.secrets.ckan.ckan_admin_password_secret)+envSource.secretKeyRef.withKey("password"),
            CKANEXT__KEYCLOAK__CLIENT_SECRET_KEY: envSource.secretKeyRef.withName(pim.keycloak.KC_CKAN_CLIENT_NAME+"-client-secret")+envSource.secretKeyRef.withKey("secret"),
            CKAN___BEAKER__SESSION__SECRET: envSource.secretKeyRef.withName(config.secrets.ckan.ckan_auth_secret)+envSource.secretKeyRef.withKey("session-key"),
            CKAN___API_TOKEN__JWT__ENCODE__SECRET: envSource.secretKeyRef.withName(config.secrets.ckan.ckan_auth_secret)+envSource.secretKeyRef.withKey("jwt-key"),
            CKAN___API_TOKEN__JWT__DECODE__SECRET: envSource.secretKeyRef.withName(config.secrets.ckan.ckan_auth_secret)+envSource.secretKeyRef.withKey("jwt-key"),
            # Create secret env vars in order to access it and construct required URLs.
            A_CKAN_DB_PASSWORD: envSource.secretKeyRef.withName(config.secrets.db.ckan_db_password_secret)+envSource.secretKeyRef.withKey("password"),
            A_DATASTORE_DB_PASSWORD: envSource.secretKeyRef.withName(config.secrets.db.datastore_db_password_secret)+envSource.secretKeyRef.withKey("password"),

            # Construct db connection URLs.
            local _DB_HOST = {host: pim.db.POSTGRES_HOST},
            local _CKAN_U = _DB_HOST+{user: pim.db.CKAN_DB_USER, password: "$(A_CKAN_DB_PASSWORD)"},
            local _DS_U = _DB_HOST+{user: pim.db.DATASTORE_READONLY_USER, password: "$(A_DATASTORE_DB_PASSWORD)"},
            local psqlURI = "postgresql://%(user)s:%(password)s@%(host)s/%(db)s",

            CKAN_SQLALCHEMY_URL: psqlURI % (_CKAN_U + {db: pim.db.STELAR_DB}),
            CKAN_DATASTORE_WRITE_URL: psqlURI % (_CKAN_U + {db: pim.db.DATASTORE_DB}),
            CKAN_DATASTORE_READ_URL: psqlURI  % (_DS_U + {db: pim.db.DATASTORE_DB}),

            # Test database connections
            TEST_CKAN_SQLALCHEMY_URL: self.CKAN_SQLALCHEMY_URL+"_test",
            TEST_CKAN_DATASTORE_WRITE_URL: self.CKAN_DATASTORE_WRITE_URL+"_test",
            TEST_CKAN_DATASTORE_READ_URL: self.CKAN_DATASTORE_READ_URL+"_test",
        })
        + (
        container.livenessProbe.exec.withCommand(
            ["/usr/bin/curl", "--fail", "http://localhost:%s/api/3/action/status_show" % pim.ports.CKAN]
            )
        + container.livenessProbe.withInitialDelaySeconds(30)
        + container.livenessProbe.withPeriodSeconds(60)
        + container.livenessProbe.withTimeoutSeconds(5)
        + container.livenessProbe.withFailureThreshold(10)
        )

        // Expose 5000
        + container.withPorts([
            containerPort.newNamed(pim.ports.CKAN, "api"),
            
        ])
        + container.withArgs(["start-server"])
        + container.withVolumeMounts([
            volumeMount.new("ckan-ini","/srv/stelar/config", false),
        ])

        + container.securityContext.withAllowPrivilegeEscalation(false)
    ],
    podLabels = {
      'app.kubernetes.io/name': 'data-catalog',
      'app.kubernetes.io/component': 'ckan',
    })
    + deploy.spec.template.spec.withInitContainers([
            podinit.wait4_redis("wait4-redis", ENV.CKAN_REDIS_URL),
            podinit.wait4_postgresql("wait4-db", pim, config),
            podinit.wait4_http("wait4-solr", "http://solr:" + pim.ports.SOLR + "/solr/")
        ])
    + deploy.spec.template.spec.withVolumes([
            vol.fromConfigMap("ckan-ini", "ckan-config", [{key: "ckan.ini", path: "ckan.ini"}])
        ])
    + deploy.spec.template.spec.securityContext.withRunAsUser(92)
    + deploy.spec.template.spec.securityContext.withRunAsGroup(92)
    + deploy.spec.template.spec.securityContext.withFsGroup(92);


/*********************
    The SOLR deployment.

    It requires
    (b) a volume for storing various data
    (c) the deployment itself
 */



local pvc_solr_data(pim) = 
    pvol.pvcWithDynamicStorage("solr-data", 
        "5Gi", pim.dynamic_volume_storage_class);



local solr_deployment(pim) = stateful.new(name="solr", containers = [
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
            containerPort.newNamed(pim.ports.SOLR, "solr"),
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

local datapusher_deployment(pim) = deploy.new(
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

    manifest(pim, config): {
        ckan: [
            ckan_deployment(pim, config),
            svcs.headlessService.new("ckan", "ckan", pim.ports.CKAN, "api")
        ],

        solr: [
            pvc_solr_data(pim), 
            solr_deployment(pim),
            svcs.headlessService.new("solr", "solr", pim.ports.SOLR, "solr")
        ],

        local datapusher_dep = datapusher_deployment(pim),
        datapusher: [
            datapusher_dep,
            svcs.serviceFor(datapusher_dep)
        ],

    }
}

