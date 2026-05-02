local k = import "../../../util/k.libsonnet";
local pim = import "../../pim.libsonnet";
local system_pim = import "../../../system/pim.libsonnet";

local cmap = k.core.v1.configMap;

local hostname(config) =
  config.endpoint.SCHEME + "://" + config.endpoint.KEYCLOAK_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN;

local keycloak_config(config) = {
  local db_url = "jdbc:postgresql://%(host)s:%(port)s/%(db)s" % {
    host: system_pim.db.POSTGRES_HOST,
    port: system_pim.ports.PG,
    db: system_pim.db.STELAR_DB,
  },
  KC_DB: pim.keycloak.DB_TYPE,
  KC_DB_URL: db_url,
  KC_DB_USERNAME: system_pim.db.KEYCLOAK_DB_USER,
  KC_DB_SCHEMA: system_pim.db.KEYCLOAK_DB_SCHEMA,
  KEYCLOAK_ADMIN: pim.keycloak.KEYCLOAK_ADMIN,
  KC_HOSTNAME: hostname(config),
  KC_HOSTNAME_ADMIN: hostname(config),
  JDBC_PARAMS: pim.keycloak.JDBC_PARAMS,
  KC_HTTP_ENABLED: pim.keycloak.KC_HTTP_ENABLED,
  KC_HEALTH_ENABLED: pim.keycloak.KC_HEALTH_ENABLED,
  KC_HOSTNAME_BACKCHANNEL_DYNAMIC: pim.keycloak.KC_HOSTNAME_BACKCHANNEL_DYNAMIC,
};

{
  new(config):
    cmap.new("kc-cmap")
    + cmap.withData(keycloak_config(config)),
}
