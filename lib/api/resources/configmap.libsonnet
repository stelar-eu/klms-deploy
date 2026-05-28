// Core ConfigMap constructor for the stelarapi component.
local k = import "../../util/k.libsonnet";

local configMap = k.core.v1.configMap;

local api_config(config) = {
  POSTGRES_HOST: config.postgres.POSTGRES_HOST,
  POSTGRES_PORT: std.toString(config.postgres.PORT),
  POSTGRES_USER: config.postgres.CKAN_DB_USER,
  POSTGRES_DB: config.postgres.STELAR_DB,

  CKAN_SITE_URL: "http://ckan:%d" % config.ckan.PORT,
  SPARQL_ENDPOINT: "http://ontop:%d/sparql" % config.ontop.PORT,

  KEYCLOAK_URL: "http://keycloak:" + std.toString(config.keycloak.PORT),
  KEYCLOAK_CLIENT_ID: config.keycloak.KC_API_CLIENT_NAME,
  REALM_NAME: config.keycloak.REALM,

  KLMS_DOMAIN_NAME: config.ROOT_DOMAIN,
  MAIN_INGRESS_SUBDOMAIN: config.PRIMARY_SUBDOMAIN,
  KEYCLOAK_SUBDOMAIN: config.keycloak.SUBDOMAIN,
  MINIO_API_SUBDOMAIN: config.minio.API_SUBDOMAIN,
  REGISTRY_SUBDOMAIN: config.quay.SUBDOMAIN,

  MINIO_API_EXT_URL: "%(SCHEME)s://%(MINIO_API_SUBDOMAIN)s.%(ROOT_DOMAIN)s" % {
    SCHEME: config.SCHEME,
    MINIO_API_SUBDOMAIN: config.minio.API_SUBDOMAIN,
    ROOT_DOMAIN: config.ROOT_DOMAIN,
  },
  KEYCLOAK_EXT_URL: "%(SCHEME)s://%(KEYCLOAK_SUBDOMAIN)s.%(ROOT_DOMAIN)s" % {
    SCHEME: config.SCHEME,
    KEYCLOAK_SUBDOMAIN: config.keycloak.SUBDOMAIN,
    ROOT_DOMAIN: config.ROOT_DOMAIN,
  },
  KEYCLOAK_ISSUER_URL: self.KEYCLOAK_EXT_URL + "/realms/" + config.keycloak.REALM,
  MAIN_EXT_URL: "%(SCHEME)s://%(PRIMARY_SUBDOMAIN)s.%(ROOT_DOMAIN)s" % {
    SCHEME: config.SCHEME,
    PRIMARY_SUBDOMAIN: config.PRIMARY_SUBDOMAIN,
    ROOT_DOMAIN: config.ROOT_DOMAIN,
  },
  REGISTRY_EXT_URL: "%(SCHEME)s://%(REGISTRY_SUBDOMAIN)s.%(ROOT_DOMAIN)s" % {
    SCHEME: config.SCHEME,
    REGISTRY_SUBDOMAIN: config.quay.SUBDOMAIN,
    ROOT_DOMAIN: config.ROOT_DOMAIN,
  },
  REGISTRY_API: "http://quay:%d" % config.quay.PORT,

  MINIO_DOMAIN: config.minio.API_DOMAIN,
  MINIO_ROOT_USER: config.minio.MINIO_ROOT_USER,
  MINIO_CONSOLE_URL: config.minio.S3_CONSOLE_URL,
  MC_INSECURE: config.minio.INSECURE_MC_CLIENT,

  FLASK_APPLICATION_ROOT: config.api.FLASK_ROOT,
  FLASK_RUN_PORT: std.toString(config.api.PORT),
  API_URL: config.api.INTERNAL_URL,

  ENABLE_LLM_SEARCH: if std.objectHas(config, "llm_search") then "true" else "false",
  LLM_SEARCH_URL: if std.objectHas(config, "llm_search") then config.llm_search.INTERNAL_URL else "",

  SMTP_USERNAME: config.api.SMTP_USERNAME,
  SMTP_SERVER: config.api.SMTP_SERVER,
  SMTP_PORT: config.api.SMTP_PORT,
  EXECUTION_ENGINE: config.api.EXEC_ENGINE,
};

{
  new(config):
    configMap.new("api-config-map")
    + configMap.withData(api_config(config))
}
