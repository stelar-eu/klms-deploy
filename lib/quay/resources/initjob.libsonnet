// Core init-job constructor for the registry component.
local k = import "../../util/k.libsonnet";
local podinit = import "../../util/podinit.libsonnet";

local job = k.batch.v1.job;
local container = k.core.v1.container;
local envSource = k.core.v1.envVarSource;

{
  new(config):
    local keycloak_external_url = config.SCHEME + "://" + config.keycloak.SUBDOMAIN + "." + config.ROOT_DOMAIN;
    job.new("quayinit")
    + job.metadata.withLabels({
      "app.kubernetes.io/name": "quay-init",
      "app.kubernetes.io/component": "quayinit",
    })
    + job.spec.template.spec.withContainers([
      container.new("quayinit-container", config.quay.INIT_IMAGE)
      + container.withImagePullPolicy("Always")
      + container.withEnvMap({
        KUBE_NAMESPACE: config.namespace,
        KC_ISSUER: keycloak_external_url + "/realms/" + config.keycloak.REALM + "/",
        KC_QUAY_PUSHERS: config.quay.QUAY_PUSHERS_ROLE,
        KC_QUAY_PULLERS: config.quay.QUAY_PULLERS_ROLE,
        KC_QUAY_GROUP_CLAIM: config.quay.KC_ROLES_CLAIM,
        KC_QUAY_CLIENT_NAME: config.keycloak.KC_API_CLIENT_NAME,
        KC_QUAY_CLIENT_SECRET: envSource.secretKeyRef.withName(config.keycloak.KC_API_CLIENT_NAME + "-client-secret") + envSource.secretKeyRef.withKey("secret"),
        KC_ADMIN_USER: config.keycloak.KEYCLOAK_ADMIN,
        KC_ADMIN_PASSWORD: envSource.secretKeyRef.withName(config.keycloak.KEYCLOAK_ROOT_PASSWORD_SECRET_NAME) + envSource.secretKeyRef.withKey("password"),
        KC_REALM: config.keycloak.REALM,
        DB_HOST: config.postgres.POSTGRES_HOST,
        DB_NAME: config.postgres.QUAY_DB,
        DB_USER: config.postgres.QUAY_DB_USER,
        DB_PASSWORD: envSource.secretKeyRef.withName(config.postgres.QUAY_DB_PASSWORD_SECRET_NAME) + envSource.secretKeyRef.withKey("password"),
        MINIO_HOST: config.minio.API_DOMAIN,
        MINIO_ROOT_USER: config.minio.MINIO_ROOT_USER,
        MINIO_ROOT_PASSWORD: envSource.secretKeyRef.withName(config.minio.MINIO_ROOT_PASSWORD_SECRET_NAME) + envSource.secretKeyRef.withKey("password"),
        MC_INSECURE: std.toString(config.minio.INSECURE_MC_CLIENT),
        MINIO_REGISTRY_BUCKET: config.quay.MINIO_BUCKET,
        QUAY_SERVER_HOSTNAME: config.quay.SUBDOMAIN + "." + config.ROOT_DOMAIN,
        QUAY_REDIS_HOSTNAME: "redis",
        QUAY_REDIS_PORT: std.toString(config.redis.PORT),
      })
    ])
    + job.spec.template.spec.withInitContainers([
      podinit.wait4_postgresql("wait4-db", config),
      podinit.wait4_redis("wait4-redis", "redis://redis:" + std.toString(config.redis.PORT) + "/1"),
      podinit.wait4_http("wait4-keycloak", "http://keycloak:9000/health/ready"),
    ])
    + job.spec.template.spec.withServiceAccountName("sysinit")
    + job.spec.template.spec.withRestartPolicy("Never")
}
