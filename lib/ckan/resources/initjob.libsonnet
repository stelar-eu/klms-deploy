// Core init-job constructor for the ckan component.
local k = import "../../util/k.libsonnet";
local podinit = import "../../util/podinit.libsonnet";

local job = k.batch.v1.job;
local container = k.core.v1.container;
local envSource = k.core.v1.envVarSource;

local env(config) = {
  CKAN_VERSION: config.ckan.CKAN_VERSION,
  CKAN_PORT: config.ckan.CKAN_PORT,
  CKAN_PORT_HOST: config.ckan.CKAN_PORT_HOST,
  CKAN__ROOT_PATH: config.ckan.CKAN__ROOT_PATH,
  CKAN_SITE_ID: config.ckan.CKAN_SITE_ID,
  CKAN_SYSADMIN_NAME: config.ckan.CKAN_SYSADMIN_NAME,
  CKAN_SYSADMIN_EMAIL: config.ckan.CKAN_SYSADMIN_EMAIL,
  CKAN_STORAGE_PATH: config.ckan.CKAN_STORAGE_PATH,
  CKAN_SMTP_SERVER: config.ckan.CKAN_SMTP_SERVER,
  CKAN_SMTP_STARTTLS: config.ckan.CKAN_SMTP_STARTTLS,
  CKAN_SMTP_USER: config.ckan.CKAN_SMTP_USER,
  CKAN_SMTP_PASSWORD: config.ckan.CKAN_SMTP_PASSWORD,
  CKAN_SMTP_MAIL_FROM: config.ckan.CKAN_SMTP_MAIL_FROM,
  CKAN__PLUGINS: config.ckan.CKAN__PLUGINS,
  CKANEXT__SPATIAL__COMMON_MAP__TYPE: config.ckan.CKANEXT__SPATIAL__COMMON_MAP__TYPE,
  CKANEXT__SPATIAL__COMMON_MAP__CUSTOM__URL: config.ckan.CKANEXT__SPATIAL__COMMON_MAP__CUSTOM__URL,
  CKANEXT__SPATIAL__COMMON_MAP__ATTRIBUTION: config.ckan.CKANEXT__SPATIAL__COMMON_MAP__ATTRIBUTION,
  TZ: config.ckan.TZ,
  CKAN__DATAPUSHER__CALLBACK_URL_BASE: config.ckan.CKAN__DATAPUSHER__CALLBACK_URL_BASE,
  DATAPUSHER_REWRITE_URL: config.ckan.DATAPUSHER_REWRITE_URL,
  CKAN__HARVEST__MQ__TYPE: config.redis.CKAN__HARVEST__MQ__TYPE,
  CKAN__HARVEST__MQ__HOSTNAME: config.redis.CKAN__HARVEST__MQ__HOSTNAME,
  CKAN__HARVEST__MQ__PORT: config.redis.CKAN__HARVEST__MQ__PORT,
  CKAN__HARVEST__MQ__REDIS_DB: config.redis.CKAN__HARVEST__MQ__REDIS_DB,
  CKAN_REDIS_URL: config.redis.CKAN_REDIS_URL,
  TEST_CKAN_REDIS_URL: config.redis.TEST_CKAN_REDIS_URL,
  CKAN_DATAPUSHER_URL: config.datapusher.CKAN_DATAPUSHER_URL,
  DATAPUSHER_REWRITE_RESOURCES: config.datapusher.DATAPUSHER_REWRITE_RESOURCES,
  CKAN_SOLR_URL: config.solr.CKAN_SOLR_URL,
  TEST_CKAN_SOLR_URL: config.solr.TEST_CKAN_SOLR_URL,
};

local keycloak_config(config) = {
  CKANEXT__KEYCLOAK__SERVER_URL: config.SCHEME + "://" + config.keycloak.SUBDOMAIN + "." + config.ROOT_DOMAIN,
  CKANEXT__KEYCLOAK__CLIENT_ID: config.keycloak.KC_CKAN_CLIENT_NAME,
  CKANEXT__KEYCLOAK__REALM_NAME: config.keycloak.REALM,
  CKANEXT__KEYCLOAK__REDIRECT_URI: config.SCHEME + "://" + config.PRIMARY_SUBDOMAIN + "." + config.ROOT_DOMAIN + config.ckan.CKAN__ROOT_PATH + "/user/sso_login",
  CKANEXT__KEYCLOAK__BUTTON_STYLE: config.ckan.CKANEXT__KEYCLOAK__BUTTON_STYLE,
  CKANEXT__KEYCLOAK__ENABLE_CKAN_INTERNAL_LOGIN: config.ckan.CKANEXT__KEYCLOAK__ENABLE_CKAN_INTERNAL_LOGIN,
};

local namespace(config) =
  assert std.objectHas(config, "namespace") : "config.namespace is required for the ckan init job";
  config.namespace;

{
  new(config):
    job.new("ckaninit")
    + job.metadata.withLabels({
      "app.kubernetes.io/name": "ckan-init",
      "app.kubernetes.io/component": "ckaninit",
    })
    + job.spec.template.spec.withContainers([
      container.new("ckaninit-container", config.ckan.IMAGE)
      + container.withImagePullPolicy("Always")
      + container.withArgs(["setup"])
      + container.withEnvMap(env(config) + keycloak_config(config) + {
        CKAN___BEAKER__SESSION__SECRET: envSource.secretKeyRef.withName(config.ckan.CKAN_AUTH_SECRET_NAME) + envSource.secretKeyRef.withKey("session-key"),
        CKAN___API_TOKEN__JWT__ENCODE__SECRET: envSource.secretKeyRef.withName(config.ckan.CKAN_AUTH_SECRET_NAME) + envSource.secretKeyRef.withKey("jwt-key"),
        CKAN___API_TOKEN__JWT__DECODE__SECRET: envSource.secretKeyRef.withName(config.ckan.CKAN_AUTH_SECRET_NAME) + envSource.secretKeyRef.withKey("jwt-key"),
        CKANEXT__KEYCLOAK__CLIENT_SECRET_KEY: envSource.secretKeyRef.withName(config.keycloak.KC_CKAN_CLIENT_NAME + "-client-secret") + envSource.secretKeyRef.withKey("secret"),
        KUBE_NAMESPACE: namespace(config),
        CKAN_SITE_URL: config.SCHEME + "://" + config.PRIMARY_SUBDOMAIN + "." + config.ROOT_DOMAIN,
        CKAN_SYSADMIN_PASSWORD: envSource.secretKeyRef.withName(config.ckan.CKAN_ADMIN_PASSWORD_SECRET_NAME) + envSource.secretKeyRef.withKey("password"),
        A_CKAN_DB_PASSWORD: envSource.secretKeyRef.withName(config.postgres.CKAN_DB_PASSWORD_SECRET_NAME) + envSource.secretKeyRef.withKey("password"),
        A_DATASTORE_DB_PASSWORD: envSource.secretKeyRef.withName(config.postgres.DATASTORE_DB_PASSWORD_SECRET_NAME) + envSource.secretKeyRef.withKey("password"),
        STELAR_SYSADMIN_ID: envSource.secretKeyRef.withName("stelar-admin-id") + envSource.secretKeyRef.withKey("id"),

        local _DB_HOST = { host: config.postgres.POSTGRES_HOST },
        local _CKAN_U = _DB_HOST + { user: config.postgres.CKAN_DB_USER, password: "$(A_CKAN_DB_PASSWORD)" },
        local _DS_U = _DB_HOST + { user: config.postgres.DATASTORE_READONLY_USER, password: "$(A_DATASTORE_DB_PASSWORD)" },
        local psqlURI = "postgresql://%(user)s:%(password)s@%(host)s/%(db)s",

        CKAN_SQLALCHEMY_URL: psqlURI % (_CKAN_U + { db: config.postgres.STELAR_DB }),
        CKAN_DATASTORE_WRITE_URL: psqlURI % (_CKAN_U + { db: config.postgres.DATASTORE_DB }),
        CKAN_DATASTORE_READ_URL: psqlURI % (_DS_U + { db: config.postgres.DATASTORE_DB }),
        TEST_CKAN_SQLALCHEMY_URL: self.CKAN_SQLALCHEMY_URL + "_test",
        TEST_CKAN_DATASTORE_WRITE_URL: self.CKAN_DATASTORE_WRITE_URL + "_test",
        TEST_CKAN_DATASTORE_READ_URL: self.CKAN_DATASTORE_READ_URL + "_test",
      })
    ])
    + job.spec.template.spec.withInitContainers([
      podinit.wait4_postgresql("wait4-db", config),
      podinit.wait4_http("wait4-solr", "http://%s:%s%s" % ["solr", config.solr.PORT, "/solr/"]),
      podinit.wait4_redis("wait4-redis", config.redis.CKAN_REDIS_URL),
    ])
    + job.spec.template.spec.withServiceAccountName("sysinit")
    + job.spec.template.spec.withRestartPolicy("Never")
}
