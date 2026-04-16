local k = import "../../util/k.libsonnet";
local podinit = import "../../util/podinit.libsonnet";

local job = k.batch.v1.job;
local container = k.core.v1.container;
local volumeMount = k.core.v1.volumeMount;
local vol = k.core.v1.volume;
local envSource = k.core.v1.envVarSource;

local KEYCLOAK_CONFIG(pim, config) = {
    CKANEXT__KEYCLOAK__SERVER_URL: config.endpoint.SCHEME + "://" + config.endpoint.KEYCLOAK_SUBDOMAIN + '.' + config.endpoint.ROOT_DOMAIN,
    CKANEXT__KEYCLOAK__CLIENT_ID: pim.keycloak.KC_CKAN_CLIENT_NAME,
    CKANEXT__KEYCLOAK__REALM_NAME: pim.keycloak.REALM,
    CKANEXT__KEYCLOAK__REDIRECT_URI: config.endpoint.SCHEME + "://" + config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN + "/dc/user/sso_login",
    CKANEXT__KEYCLOAK__BUTTON_STYLE: "",
    CKANEXT__KEYCLOAK__ENABLE_CKAN_INTERNAL_LOGIN: "True",
};

{
    manifest(pim, config): {
        ckaninitjob: job.new("ckaninit")
            + job.metadata.withLabels({
                'app.kubernetes.io/name': 'ckan-init',
                'app.kubernetes.io/component': 'ckaninit',
            })
            + job.spec.template.spec.withContainers(containers=[
                container.new("ckaninit-container", pim.images.CKAN_IMAGE)
                + container.withImagePullPolicy("Always")
                + container.withArgs(["setup"])
                + container.withEnvMap(KEYCLOAK_CONFIG(pim, config) + {
                    CKAN___BEAKER__SESSION__SECRET: envSource.secretKeyRef.withName(config.secrets.ckan.ckan_auth_secret) + envSource.secretKeyRef.withKey("session-key"),
                    CKAN___API_TOKEN__JWT__ENCODE__SECRET: envSource.secretKeyRef.withName(config.secrets.ckan.ckan_auth_secret) + envSource.secretKeyRef.withKey("jwt-key"),
                    CKAN___API_TOKEN__JWT__DECODE__SECRET: envSource.secretKeyRef.withName(config.secrets.ckan.ckan_auth_secret) + envSource.secretKeyRef.withKey("jwt-key"),
                    CKANEXT__KEYCLOAK__CLIENT_SECRET_KEY: envSource.secretKeyRef.withName(pim.keycloak.KC_CKAN_CLIENT_NAME + "-client-secret") + envSource.secretKeyRef.withKey("secret"),
                    CKAN_VERSION: '2.10.0',
                    CKAN_SYSADMIN_NAME: "admin",
                    CKAN_SYSADMIN_EMAIL: "info@stelar.gr",
                    CKAN_STORAGE_PATH: "/var/lib/ckan",
                    KUBE_NAMESPACE: pim.namespace,
                    CKAN__PLUGINS: "envvars image_view text_view recline_view datastore datapusher"
                        + " keycloak"
                        + " resource_proxy geo_view"
                        + " spatial_metadata spatial_query",
                    CKAN__HARVEST__MQ__TYPE: "redis",
                    CKAN__HARVEST__MQ__HOSTNAME: "redis",
                    CKAN__HARVEST__MQ__PORT: "6379",
                    CKAN__HARVEST__MQ__REDIS_DB: "1",
                    TZ: "UTC",
                    CKANEXT__SPATIAL__COMMON_MAP__TYPE: "custom",
                    CKANEXT__SPATIAL__COMMON_MAP__CUSTOM__URL: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                    CKANEXT__SPATIAL__COMMON_MAP__ATTRIBUTION: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                    CKAN_SITE_URL: config.endpoint.SCHEME + "://" + config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN,
                    CKAN_SYSADMIN_PASSWORD: envSource.secretKeyRef.withName(config.secrets.ckan.ckan_admin_password_secret) + envSource.secretKeyRef.withKey("password"),
                    A_CKAN_DB_PASSWORD: envSource.secretKeyRef.withName(config.secrets.db.ckan_db_password_secret) + envSource.secretKeyRef.withKey("password"),
                    A_DATASTORE_DB_PASSWORD: envSource.secretKeyRef.withName(config.secrets.db.datastore_db_password_secret) + envSource.secretKeyRef.withKey("password"),
                    STELAR_SYSADMIN_ID: envSource.secretKeyRef.withName("stelar-admin-id") + envSource.secretKeyRef.withKey("id"),
                    local _DB_HOST = {host: pim.db.POSTGRES_HOST},
                    local _CKAN_U = _DB_HOST + {user: pim.db.CKAN_DB_USER, password: "$(A_CKAN_DB_PASSWORD)"},
                    local _DS_U = _DB_HOST + {user: pim.db.DATASTORE_READONLY_USER, password: "$(A_DATASTORE_DB_PASSWORD)"},
                    local psqlURI = "postgresql://%(user)s:%(password)s@%(host)s/%(db)s",
                    CKAN_SQLALCHEMY_URL: psqlURI % (_CKAN_U + {db: pim.db.STELAR_DB}),
                    CKAN_DATASTORE_WRITE_URL: psqlURI % (_CKAN_U + {db: pim.db.DATASTORE_DB}),
                    CKAN_DATASTORE_READ_URL: psqlURI % (_DS_U + {db: pim.db.DATASTORE_DB}),
                    TEST_CKAN_SQLALCHEMY_URL: self.CKAN_SQLALCHEMY_URL + "_test",
                    TEST_CKAN_DATASTORE_WRITE_URL: self.CKAN_DATASTORE_WRITE_URL + "_test",
                    TEST_CKAN_DATASTORE_READ_URL: self.CKAN_DATASTORE_READ_URL + "_test",
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
                podinit.wait4_http("wait4-solr", "http://solr:" + pim.ports.SOLR + "/solr/"),
                podinit.wait4_redis("wait4-redis", "redis://redis:6379/1"),
            ])
            + job.spec.template.spec.withServiceAccountName("sysinit")
            + job.spec.template.spec.withRestartPolicy("Never"),
    }
}
