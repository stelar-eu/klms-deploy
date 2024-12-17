local k = import "k.libsonnet";
local podinit = import "podinit.libsonnet";
local rbac = import "rbac.libsonnet";

local deploy = k.apps.v1.deployment;
local job = k.batch.v1.job;
local container = k.core.v1.container;
local stateful = k.apps.v1.statefulSet;
local containerPort = k.core.v1.containerPort;
local pod = k.core.v1.pod;
local port = k.core.v1.containerPort;
local volumeMount = k.core.v1.volumeMount;
local vol = k.core.v1.volume;
local cmap = k.core.v1.configMap;
local service = k.core.v1.service;
local secret = k.core.v1.secret;
local envSource = k.core.v1.envVarSource;
local volumeMount = k.core.v1.volumeMount;



local KEYCLOAK_CONFIG(pim,config) = {
    CKANEXT__KEYCLOAK__SERVER_URL: config.endpoint.SCHEME+"://"+config.endpoint.KEYCLOAK_SUBDOMAIN+'.'+config.endpoint.ROOT_DOMAIN, 
    CKANEXT__KEYCLOAK__CLIENT_ID: pim.keycloak.KC_CKAN_CLIENT_NAME,
    CKANEXT__KEYCLOAK__REALM_NAME:  pim.keycloak.REALM, 
    CKANEXT__KEYCLOAK__REDIRECT_URI:  config.endpoint.SCHEME+"://"+config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN + "/dc/user/sso_login",
    CKANEXT__KEYCLOAK__BUTTON_STYLE:  "",
    CKANEXT__KEYCLOAK__ENABLE_CKAN_INTERNAL_LOGIN: "True",
};

{
    manifest(pim,config): {

        kcinitjob: job.new("kcinit")
            + job.metadata.withLabels({
                'app.kubernetes.io/name': 'kc-init',
                'app.kubernetes.io/component': 'kcinit',
            })
            + job.spec.template.spec.withContainers(containers=[
                container.new("kcinit-container", pim.images.KC_INIT)
                + container.withImagePullPolicy("Always")
                + container.withEnvMap({
                    MINIO_ROOT_USER: pim.minio.MINIO_ROOT_USER,
                    MINIO_ROOT_PASSWORD: envSource.secretKeyRef.withName(config.secrets.minio.minio_root_password_secret)+envSource.secretKeyRef.withKey("password"),
                    MINIO_API_DOMAIN: config.minio.API_DOMAIN,
                    MINIO_CONSOLE_DOMAIN: config.minio.CONSOLE_DOMAIN,
                    MINIO_INSECURE_MC: config.minio.INSECURE_MC_CLIENT,
                    KEYCLOAK_ADMIN : pim.keycloak.KEYCLOAK_ADMIN,
                    KEYCLOAK_ADMIN_PASSWORD : envSource.secretKeyRef.withName(config.secrets.keycloak.root_password_secret)+envSource.secretKeyRef.withKey("password"),
                    KEYCLOAK_REALM: pim.keycloak.REALM,
                    KEYCLOAK_DOMAIN_NAME: config.endpoint.SCHEME+"://"+config.endpoint.KEYCLOAK_SUBDOMAIN+"."+config.endpoint.ROOT_DOMAIN,
                    KEYCLOAK_PORT: std.toString(pim.ports.KEYCLOAK),
                    KC_API_CLIENT_NAME: pim.keycloak.KC_API_CLIENT_NAME,
                    KC_MINIO_CLIENT_NAME: pim.keycloak.KC_MINIO_CLIENT_NAME,
                    KC_CKAN_CLIENT_NAME: pim.keycloak.KC_CKAN_CLIENT_NAME,
                    KUBE_NAMESPACE: pim.namespace,
                    KC_API_CLIENT_REDIRECT: config.endpoint.SCHEME+"://"+config.endpoint.PRIMARY_SUBDOMAIN+"."+config.endpoint.ROOT_DOMAIN+"/*",
                    KC_MINIO_CLIENT_REDIRECT: config.endpoint.SCHEME+"://"+config.endpoint.PRIMARY_SUBDOMAIN+"."+config.endpoint.ROOT_DOMAIN+"/s3/oauth_callback",
                    KC_CKAN_CLIENT_REDIRECT: config.endpoint.SCHEME+"://"+config.endpoint.PRIMARY_SUBDOMAIN+"."+config.endpoint.ROOT_DOMAIN+"/*",
                    KC_API_CLIENT_HOME_URL: config.endpoint.SCHEME+"://"+config.endpoint.PRIMARY_SUBDOMAIN+"."+config.endpoint.ROOT_DOMAIN+"/stelar",
                    KC_MINIO_CLIENT_HOME_URL:config.endpoint.SCHEME+"://"+config.endpoint.PRIMARY_SUBDOMAIN+"."+config.endpoint.ROOT_DOMAIN+"/s3/console",
                    KC_CKAN_CLIENT_HOME_URL: config.endpoint.SCHEME+"://"+config.endpoint.PRIMARY_SUBDOMAIN+"."+config.endpoint.ROOT_DOMAIN+"/dc",
                    KC_API_CLIENT_ROOT_URL: config.endpoint.SCHEME+"://"+config.endpoint.PRIMARY_SUBDOMAIN+"."+config.endpoint.ROOT_DOMAIN+"/stelar",
                    KC_MINIO_CLIENT_ROOT_URL: config.endpoint.SCHEME+"://"+config.endpoint.PRIMARY_SUBDOMAIN+"."+config.endpoint.ROOT_DOMAIN+"/s3/console",
                    KC_CKAN_CLIENT_ROOT_URL: config.endpoint.SCHEME+"://"+config.endpoint.PRIMARY_SUBDOMAIN+"."+config.endpoint.ROOT_DOMAIN+"/dc",
                })
            ])
            + job.spec.template.spec.withInitContainers([
                podinit.wait4_postgresql("wait4-db", pim, config),
                podinit.wait4_http("wait4-keycloak", "http://keycloak:9000/health/ready"),
            ])
            + job.spec.template.spec.withServiceAccountName("sysinit")
            + job.spec.template.spec.withRestartPolicy("Never"),





         apiinitjob: job.new("apiinit")
            + job.metadata.withLabels({
                'app.kubernetes.io/name': 'api-init',
                'app.kubernetes.io/component': 'apiinit',
            })
            + job.spec.template.spec.withContainers(containers=[
                container.new("apiinit-container", pim.images.API_IMAGE)
                + container.withImagePullPolicy("Always")
                + container.withArgs(["setup-db"]) // Set how the image should be executed
                + container.withEnvMap({
                    POSTGRES_HOST: pim.db.POSTGRES_HOST,
                    POSTGRES_DB: pim.db.STELAR_DB,
                    POSTGRES_USER: pim.db.CKAN_DB_USER,
                    POSTGRES_PASSWORD: envSource.secretKeyRef.withName(config.secrets.db.ckan_db_password_secret)+envSource.secretKeyRef.withKey("password"),
                    CKAN_ADMIN_TOKEN: envSource.secretKeyRef.withName("ckan-admin-token-secret")+envSource.secretKeyRef.withKey("token"),
                })
                + container.withVolumeMounts([
                    volumeMount.new("ckan-ini","/srv/stelar/config", false),
                ])
            ])
            + job.spec.template.spec.withInitContainers([
                podinit.wait4_postgresql("wait4-db", pim, config),
            ])
            + job.spec.template.spec.withVolumes([
                vol.fromConfigMap("ckan-ini","ckan-config", [{key:"ckan.ini", path:"ckan.ini"}])
            ])
            + job.spec.template.spec.withRestartPolicy("Never"),


        ontopinitjob: job.new("ontopinit")
            + job.metadata.withLabels({
                'app.kubernetes.io/name': 'ontop-init',
                'app.kubernetes.io/component': 'ontopinit',
            })
            + job.spec.template.spec.withContainers(containers=[
                container.new("ontopinit-container", pim.images.ONTOP_IMAGE)
                + container.withImagePullPolicy("Always")
                + container.withArgs(["setup-db"]) // Set how the image should be executed
                + container.withEnvMap({
                   ONTOP_DB_USER: pim.db.CKAN_DB_USER,
                   ONTOP_DB_PASSWORD: envSource.secretKeyRef.withName(config.secrets.db.ckan_db_password_secret)+envSource.secretKeyRef.withKey("password"),
                   ONTOP_DB_HOST: pim.db.POSTGRES_HOST,
                   ONTOP_DB: pim.db.STELAR_DB,
                })
                + container.withVolumeMounts([
                    volumeMount.new("ckan-ini","/srv/stelar/config", false),
                ])
            ])
            + job.spec.template.spec.withInitContainers([
                podinit.wait4_postgresql("wait4-db", pim, config),
            ])
            + job.spec.template.spec.withVolumes([
                vol.fromConfigMap("ckan-ini","ckan-config", [{key:"ckan.ini", path:"ckan.ini"}])
            ])
            + job.spec.template.spec.withRestartPolicy("Never"),



        initrbac: rbac.namespacedRBAC("sysinit", [
            rbac.resourceRule(
                ["create","get","list","update","delete"],
                [""],
                ["secrets","configmaps"])
        ]),


        ckaninitjob: job.new("ckaninit")
            + job.metadata.withLabels({
                'app.kubernetes.io/name': 'ckan-init',
                'app.kubernetes.io/component': 'ckaninit',
            })
            + job.spec.template.spec.withContainers(containers=[
                container.new("ckaninit-container", pim.images.CKAN_IMAGE)
                + container.withImagePullPolicy("Always")
                + container.withArgs(["setup"]) // Set how the image should be executed
                + container.withEnvMap( KEYCLOAK_CONFIG(pim, config) + {
                    CKAN___BEAKER__SESSION__SECRET: 'qD-fHjSOa6xTMsAJDkfLKY-eRaYZnlI-5YBkkponncA',
                    CKAN___API_TOKEN__JWT__ENCODE__SECRET: 'string:ixORfkMa1CYT2yj1LApKM1S6GW7CUHlTjObiA5DgfXM',
                    CKAN___API_TOKEN__JWT__DECODE__SECRET: 'string:ixORfkMa1CYT2yj1LApKM1S6GW7CUHlTjObiA5DgfXM',
                    CKANEXT__KEYCLOAK__CLIENT_SECRET_KEY: envSource.secretKeyRef.withName(pim.keycloak.KC_CKAN_CLIENT_NAME+"-client-secret")+envSource.secretKeyRef.withKey("secret"),

                    CKAN_VERSION: '2.10.0',
                    CKAN_SYSADMIN_NAME: "ckan_admin",
                    CKAN_SYSADMIN_EMAIL: "vsam@softnet.tuc.gr",
                    CKAN_STORAGE_PATH: "/var/lib/ckan",
                    KUBE_NAMESPACE: pim.namespace,
                    CKAN__PLUGINS: "envvars image_view text_view recline_view datastore datapusher"
                    +" keycloak"
                    +" resource_proxy geo_view"
                    +" spatial_metadata spatial_query"
                    ,
                    CKAN__HARVEST__MQ__TYPE: "redis",
                    CKAN__HARVEST__MQ__HOSTNAME: "redis",
                    CKAN__HARVEST__MQ__PORT: "6379",
                    CKAN__HARVEST__MQ__REDIS_DB: "1",
                    TZ: "UTC",
                    # Using settings for the standard OSM tile server
                    CKANEXT__SPATIAL__COMMON_MAP__TYPE: "custom",
                    CKANEXT__SPATIAL__COMMON_MAP__CUSTOM__URL: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                    CKANEXT__SPATIAL__COMMON_MAP__ATTRIBUTION: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                    CKAN_SITE_URL: config.endpoint.SCHEME+"://"+config.endpoint.PRIMARY_SUBDOMAIN+"."+config.endpoint.ROOT_DOMAIN,
                    CKAN_SYSADMIN_PASSWORD: envSource.secretKeyRef.withName(config.secrets.ckan.ckan_admin_password_secret)+envSource.secretKeyRef.withKey("password"),
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
                    DATAPUSHER_VERSION: "0.0.20",
                    CKAN_DATAPUSHER_URL: "http://datapusher:8800",
                    CKAN__DATAPUSHER__CALLBACK_URL_BASE: "http://ckan:5000",
                    DATAPUSHER_REWRITE_RESOURCES: "True",
                    DATAPUSHER_REWRITE_URL: "http://ckan:5000",
                    CKAN_SOLR_URL: "http://solr:8983/solr/ckan",
                    TEST_CKAN_SOLR_URL: "http://solr:8983/solr/ckan",
                    CKAN_REDIS_URL: "redis://redis:6379/1",
                    TEST_CKAN_REDIS_URL: "redis://redis:6379/1",        
                })
            ])
            + job.spec.template.spec.withInitContainers([
                podinit.wait4_postgresql("wait4-db", pim, config),
                podinit.wait4_http("wait4-solr", "http://solr:"+pim.ports.SOLR+"/solr/"),
                podinit.wait4_redis("wait4-redis", "redis://redis:6379/1"),
            ])
            + job.spec.template.spec.withServiceAccountName("sysinit")
            + job.spec.template.spec.withRestartPolicy("Never"),

        
    }

}