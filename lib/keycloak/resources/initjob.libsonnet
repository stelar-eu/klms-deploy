// Core init-job constructor for the keycloak component.
local k = import "../../util/k.libsonnet";
local podinit = import "../../util/podinit.libsonnet";

local job = k.batch.v1.job;
local container = k.core.v1.container;
local envSource = k.core.v1.envVarSource;

local env(config) = {
  MINIO_ROOT_USER: config.minio.MINIO_ROOT_USER,
  MINIO_ROOT_PASSWORD: envSource.secretKeyRef.withName(config.minio.MINIO_ROOT_PASSWORD_SECRET_NAME) + envSource.secretKeyRef.withKey("password"),
  MINIO_API_DOMAIN: config.minio.API_DOMAIN,
  MINIO_CONSOLE_DOMAIN: config.minio.CONSOLE_DOMAIN,
  MINIO_INSECURE_MC: config.minio.INSECURE_MC_CLIENT,
  KEYCLOAK_ADMIN: config.keycloak.KEYCLOAK_ADMIN,
  KEYCLOAK_ADMIN_PASSWORD: envSource.secretKeyRef.withName(config.keycloak.KEYCLOAK_ROOT_PASSWORD_SECRET_NAME) + envSource.secretKeyRef.withKey("password"),
  KEYCLOAK_REALM: config.keycloak.REALM,
  KEYCLOAK_DOMAIN_NAME: config.SCHEME + "://" + config.keycloak.SUBDOMAIN + "." + config.ROOT_DOMAIN,
  KEYCLOAK_PORT: std.toString(config.keycloak.PORT),
  KC_API_CLIENT_NAME: config.keycloak.KC_API_CLIENT_NAME,
  KC_MINIO_CLIENT_NAME: config.keycloak.KC_MINIO_CLIENT_NAME,
  KC_CKAN_CLIENT_NAME: config.keycloak.KC_CKAN_CLIENT_NAME,
  KUBE_NAMESPACE: config.namespace,
  KC_API_CLIENT_REDIRECT: config.SCHEME + "://" + config.PRIMARY_SUBDOMAIN + "." + config.ROOT_DOMAIN + "/*",
  KC_MINIO_CLIENT_REDIRECT: config.SCHEME + "://" + config.PRIMARY_SUBDOMAIN + "." + config.ROOT_DOMAIN + "/s3/oauth_callback",
  KC_CKAN_CLIENT_REDIRECT: config.SCHEME + "://" + config.PRIMARY_SUBDOMAIN + "." + config.ROOT_DOMAIN + "/*",
  KC_API_CLIENT_HOME_URL: config.SCHEME + "://" + config.PRIMARY_SUBDOMAIN + "." + config.ROOT_DOMAIN + "/stelar",
  KC_MINIO_CLIENT_HOME_URL: config.SCHEME + "://" + config.PRIMARY_SUBDOMAIN + "." + config.ROOT_DOMAIN + "/s3/console",
  KC_CKAN_CLIENT_HOME_URL: config.SCHEME + "://" + config.PRIMARY_SUBDOMAIN + "." + config.ROOT_DOMAIN + "/dc",
  KC_API_CLIENT_ROOT_URL: config.SCHEME + "://" + config.PRIMARY_SUBDOMAIN + "." + config.ROOT_DOMAIN + "/stelar",
  KC_MINIO_CLIENT_ROOT_URL: config.SCHEME + "://" + config.PRIMARY_SUBDOMAIN + "." + config.ROOT_DOMAIN + "/s3/console",
  KC_CKAN_CLIENT_ROOT_URL: config.SCHEME + "://" + config.PRIMARY_SUBDOMAIN + "." + config.ROOT_DOMAIN + "/dc",
};

{
  new(config):
  job.new("kcinit")
  + job.metadata.withLabels({
    "app.kubernetes.io/name": "kc-init",
    "app.kubernetes.io/component": "kcinit",
  })
  + job.spec.template.spec.withContainers([
    container.new("kcinit-container", config.keycloak.INIT_IMAGE)
    + container.withImagePullPolicy("Always")
    + container.withEnvMap(env(config))
  ])
  + job.spec.template.spec.withInitContainers([
    podinit.wait4_postgresql("wait4-db", config),
    podinit.wait4_http("wait4-keycloak", "http://keycloak:9000/health/ready"),
  ])
  + job.spec.template.spec.withServiceAccountName("sysinit")
  + job.spec.template.spec.withRestartPolicy("Never")
}
