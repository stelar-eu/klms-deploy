local k = import "../../../util/k.libsonnet";
local pim = import "../../pim.libsonnet";
local system_pim = import "../../../system/pim.libsonnet";
local podinit = import "../../../util/podinit.libsonnet";

local job = k.batch.v1.job;
local container = k.core.v1.container;
local envSource = k.core.v1.envVarSource;

local keycloak_config(config) = {
  CKANEXT__KEYCLOAK__SERVER_URL: config.endpoint.SCHEME + "://" + config.endpoint.KEYCLOAK_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN,
  CKANEXT__KEYCLOAK__CLIENT_ID: system_pim.keycloak.KC_CKAN_CLIENT_NAME,
  CKANEXT__KEYCLOAK__REALM_NAME: system_pim.keycloak.REALM,
  CKANEXT__KEYCLOAK__REDIRECT_URI: config.endpoint.SCHEME + "://" + config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN + pim.keycloak.redirect_path,
  CKANEXT__KEYCLOAK__BUTTON_STYLE: pim.keycloak.button_style,
  CKANEXT__KEYCLOAK__ENABLE_CKAN_INTERNAL_LOGIN: pim.keycloak.enable_internal_login,
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
      container.new("ckaninit-container", pim.images.CKAN_IMAGE)
      + container.withImagePullPolicy(pim.deployment.image_pull_policy)
      + container.withArgs(["setup"])
      + container.withEnvMap(pim.env + keycloak_config(config) + {
        CKAN___BEAKER__SESSION__SECRET: envSource.secretKeyRef.withName(config.secrets.ckan.ckan_auth_secret) + envSource.secretKeyRef.withKey("session-key"),
        CKAN___API_TOKEN__JWT__ENCODE__SECRET: envSource.secretKeyRef.withName(config.secrets.ckan.ckan_auth_secret) + envSource.secretKeyRef.withKey("jwt-key"),
        CKAN___API_TOKEN__JWT__DECODE__SECRET: envSource.secretKeyRef.withName(config.secrets.ckan.ckan_auth_secret) + envSource.secretKeyRef.withKey("jwt-key"),
        CKANEXT__KEYCLOAK__CLIENT_SECRET_KEY: envSource.secretKeyRef.withName(system_pim.keycloak.KC_CKAN_CLIENT_NAME + "-client-secret") + envSource.secretKeyRef.withKey("secret"),
        KUBE_NAMESPACE: namespace(config),
        CKAN_SITE_URL: config.endpoint.SCHEME + "://" + config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN,
        CKAN_SYSADMIN_PASSWORD: envSource.secretKeyRef.withName(config.secrets.ckan.ckan_admin_password_secret) + envSource.secretKeyRef.withKey("password"),
        A_CKAN_DB_PASSWORD: envSource.secretKeyRef.withName(config.secrets.db.ckan_db_password_secret) + envSource.secretKeyRef.withKey("password"),
        A_DATASTORE_DB_PASSWORD: envSource.secretKeyRef.withName(config.secrets.db.datastore_db_password_secret) + envSource.secretKeyRef.withKey("password"),
        STELAR_SYSADMIN_ID: envSource.secretKeyRef.withName("stelar-admin-id") + envSource.secretKeyRef.withKey("id"),

        local _DB_HOST = { host: system_pim.db.POSTGRES_HOST },
        local _CKAN_U = _DB_HOST + { user: system_pim.db.CKAN_DB_USER, password: "$(A_CKAN_DB_PASSWORD)" },
        local _DS_U = _DB_HOST + { user: system_pim.db.DATASTORE_READONLY_USER, password: "$(A_DATASTORE_DB_PASSWORD)" },
        local psqlURI = "postgresql://%(user)s:%(password)s@%(host)s/%(db)s",

        CKAN_SQLALCHEMY_URL: psqlURI % (_CKAN_U + { db: system_pim.db.STELAR_DB }),
        CKAN_DATASTORE_WRITE_URL: psqlURI % (_CKAN_U + { db: system_pim.db.DATASTORE_DB }),
        CKAN_DATASTORE_READ_URL: psqlURI % (_DS_U + { db: system_pim.db.DATASTORE_DB }),
        TEST_CKAN_SQLALCHEMY_URL: self.CKAN_SQLALCHEMY_URL + "_test",
        TEST_CKAN_DATASTORE_WRITE_URL: self.CKAN_DATASTORE_WRITE_URL + "_test",
        TEST_CKAN_DATASTORE_READ_URL: self.CKAN_DATASTORE_READ_URL + "_test",
      })
    ])
    + job.spec.template.spec.withInitContainers([
      podinit.wait4_postgresql(pim.init.wait_for_db_name, system_pim, config),
      podinit.wait4_http(pim.init.wait_for_solr_name, "http://%s:%s%s" % [pim.init.solr_service_name, system_pim.ports.SOLR, pim.init.solr_path]),
      podinit.wait4_redis(pim.init.wait_for_redis_name, pim.init.redis_url),
    ])
    + job.spec.template.spec.withServiceAccountName("sysinit")
    + job.spec.template.spec.withRestartPolicy("Never"),
}
