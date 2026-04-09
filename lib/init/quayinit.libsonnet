local k = import "k.libsonnet";
local podinit = import "podinit.libsonnet";

local job = k.batch.v1.job;
local container = k.core.v1.container;
local envSource = k.core.v1.envVarSource;

{
    manifest(pim, config): {
        local keycloak_external_url = config.endpoint.SCHEME + "://" + config.endpoint.KEYCLOAK_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN,

        registryinit: job.new("quayinit")
            + job.metadata.withLabels({
                'app.kubernetes.io/name': 'quay-init',
                'app.kubernetes.io/component': 'quayinit',
            })
            + job.spec.template.spec.withContainers(containers=[
                container.new("quayinit-container", pim.images.REGISTRY_INIT)
                + container.withImagePullPolicy("Always")
                + container.withEnvMap({
                    KUBE_NAMESPACE: pim.namespace,
                    KC_ISSUER: keycloak_external_url + "/realms/" + pim.keycloak.REALM + "/",
                    KC_QUAY_PUSHERS: pim.registry.QUAY_PUSHERS_ROLE,
                    KC_QUAY_PULLERS: pim.registry.QUAY_PULLERS_ROLE,
                    KC_QUAY_GROUP_CLAIM: pim.registry.KC_ROLES_CLAIM,
                    KC_QUAY_CLIENT_NAME: pim.keycloak.KC_API_CLIENT_NAME,
                    KC_QUAY_CLIENT_SECRET: envSource.secretKeyRef.withName(pim.keycloak.KC_API_CLIENT_NAME + "-client-secret") + envSource.secretKeyRef.withKey("secret"),
                    KC_ADMIN_USER: pim.keycloak.KEYCLOAK_ADMIN,
                    KC_ADMIN_PASSWORD: envSource.secretKeyRef.withName(config.secrets.keycloak.root_password_secret) + envSource.secretKeyRef.withKey("password"),
                    KC_REALM: pim.keycloak.REALM,
                    DB_HOST: pim.db.POSTGRES_HOST,
                    DB_NAME: pim.db.QUAY_DB,
                    DB_USER: pim.db.QUAY_DB_USER,
                    DB_PASSWORD: envSource.secretKeyRef.withName(config.secrets.db.quay_db_password_secret) + envSource.secretKeyRef.withKey("password"),
                    MINIO_HOST: config.minio.API_DOMAIN,
                    MINIO_ROOT_USER: pim.minio.MINIO_ROOT_USER,
                    MINIO_ROOT_PASSWORD: envSource.secretKeyRef.withName(config.secrets.minio.minio_root_password_secret) + envSource.secretKeyRef.withKey("password"),
                    MC_INSECURE: std.toString(config.minio.INSECURE_MC_CLIENT),
                    MINIO_REGISTRY_BUCKET: pim.registry.MINIO_BUCKET,
                    QUAY_SERVER_HOSTNAME: config.endpoint.REGISTRY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN,
                    QUAY_REDIS_HOSTNAME: 'redis',
                    QUAY_REDIS_PORT: std.toString(pim.ports.REDIS),
                })
            ])
            + job.spec.template.spec.withInitContainers([
                podinit.wait4_postgresql("wait4-db", pim, config),
                podinit.wait4_redis("wait4-redis", "redis://redis:6379/1"),
                podinit.wait4_http("wait4-keycloak", "http://keycloak:9000/health/ready"),
            ])
            + job.spec.template.spec.withServiceAccountName("sysinit")
            + job.spec.template.spec.withRestartPolicy("Never"),
    }
}
