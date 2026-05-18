// Core ConfigMap constructor for the keycloak component.
local k = import "../../util/k.libsonnet";

local cmap = k.core.v1.configMap;

local hostname(config) =
  config.SCHEME + "://" + config.keycloak.SUBDOMAIN + "." + config.ROOT_DOMAIN;

local keycloak_config(config) = {
  local db_url = "jdbc:postgresql://%(host)s:%(port)s/%(db)s" % {
    host: config.postgres.POSTGRES_HOST,
    port: config.postgres.PORT,
    db: config.postgres.STELAR_DB,
  },
  KC_DB: config.keycloak.DB_TYPE,
  KC_DB_URL: db_url,
  KC_DB_USERNAME: config.postgres.KEYCLOAK_DB_USER,
  KC_DB_SCHEMA: config.postgres.KEYCLOAK_DB_SCHEMA,
  KEYCLOAK_ADMIN: config.keycloak.KEYCLOAK_ADMIN,
  KC_HOSTNAME: hostname(config),
  KC_HOSTNAME_ADMIN: hostname(config),
  JDBC_PARAMS: config.keycloak.JDBC_PARAMS,
  KC_HTTP_ENABLED: config.keycloak.KC_HTTP_ENABLED,
  KC_HEALTH_ENABLED: config.keycloak.KC_HEALTH_ENABLED,
  KC_HOSTNAME_BACKCHANNEL_DYNAMIC: config.keycloak.KC_HOSTNAME_BACKCHANNEL_DYNAMIC,
};

{
  new(config):
    cmap.new("kc-cmap")
    + cmap.withData(keycloak_config(config))
}
