// Core ConfigMap constructor for the stelarapi component.
local k = import "../../../util/k.libsonnet";
local pim = import "../../pim.libsonnet";
local system_pim = import "../../../system/pim.libsonnet";

local configMap = k.core.v1.configMap;

local api_config(config) = {
  POSTGRES_HOST: system_pim.db.POSTGRES_HOST,
  POSTGRES_PORT: std.toString(system_pim.ports.PG),
  POSTGRES_USER: system_pim.db.CKAN_DB_USER,
  POSTGRES_DB: system_pim.db.STELAR_DB,

  CKAN_SITE_URL: "http://ckan:%d" % system_pim.ports.CKAN,
  SPARQL_ENDPOINT: "http://ontop:%d/sparql" % system_pim.ports.ONTOP,

  KEYCLOAK_URL: "http://keycloak:" + std.toString(system_pim.ports.KEYCLOAK),
  KEYCLOAK_CLIENT_ID: system_pim.keycloak.KC_API_CLIENT_NAME,
  REALM_NAME: system_pim.keycloak.REALM,

  KLMS_DOMAIN_NAME: config.endpoint.ROOT_DOMAIN,
  MAIN_INGRESS_SUBDOMAIN: config.endpoint.PRIMARY_SUBDOMAIN,
  KEYCLOAK_SUBDOMAIN: config.endpoint.KEYCLOAK_SUBDOMAIN,
  MINIO_API_SUBDOMAIN: config.endpoint.MINIO_API_SUBDOMAIN,
  REGISTRY_SUBDOMAIN: config.endpoint.REGISTRY_SUBDOMAIN,

  MINIO_API_EXT_URL: "%(SCHEME)s://%(MINIO_API_SUBDOMAIN)s.%(ROOT_DOMAIN)s" % config.endpoint,
  KEYCLOAK_EXT_URL: "%(SCHEME)s://%(KEYCLOAK_SUBDOMAIN)s.%(ROOT_DOMAIN)s" % config.endpoint,
  KEYCLOAK_ISSUER_URL: self.KEYCLOAK_EXT_URL + "/realms/" + system_pim.keycloak.REALM,
  MAIN_EXT_URL: "%(SCHEME)s://%(PRIMARY_SUBDOMAIN)s.%(ROOT_DOMAIN)s" % config.endpoint,
  REGISTRY_EXT_URL: "%(SCHEME)s://%(REGISTRY_SUBDOMAIN)s.%(ROOT_DOMAIN)s" % config.endpoint,
  REGISTRY_API: "http://quay:%d" % pim.ports.QUAY,

  MINIO_DOMAIN: config.minio.API_DOMAIN,
  MINIO_ROOT_USER: system_pim.minio.MINIO_ROOT_USER,
  MINIO_CONSOLE_URL: config.api.S3_CONSOLE_URL,
  MC_INSECURE: config.minio.INSECURE_MC_CLIENT,

  FLASK_APPLICATION_ROOT: pim.api.FLASK_ROOT,
  FLASK_RUN_PORT: std.toString(pim.ports.STELARAPI),
  API_URL: pim.api.INTERNAL_URL,

  ENABLE_LLM_SEARCH: config.llm_search.ENABLE_LLM_SEARCH,
  LLM_SEARCH_URL: pim.llm_search.INTERNAL_URL,

  SMTP_USERNAME: config.api.SMTP_USERNAME,
  SMTP_SERVER: config.api.SMTP_SERVER,
  SMTP_PORT: config.api.SMTP_PORT,
  EXECUTION_ENGINE: pim.api.EXEC_ENGINE,
};

{
  new(config):
    configMap.new("api-config-map")
    + configMap.withData(api_config(config)),
}
