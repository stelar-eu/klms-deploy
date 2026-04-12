local k = import "k.libsonnet";
local podinit = import "podinit.libsonnet";

local job = k.batch.v1.job;
local container = k.core.v1.container;
local envSource = k.core.v1.envVarSource;

{
    env(pim, config): {
        MINIO_ROOT_USER: pim.minio.MINIO_ROOT_USER,
        MINIO_ROOT_PASSWORD: envSource.secretKeyRef.withName(config.secrets.minio.minio_root_password_secret) + envSource.secretKeyRef.withKey("password"),
        MINIO_API_DOMAIN: config.minio.API_DOMAIN,
        MINIO_CONSOLE_DOMAIN: config.minio.CONSOLE_DOMAIN,
        MINIO_INSECURE_MC: config.minio.INSECURE_MC_CLIENT,
        KEYCLOAK_ADMIN: pim.keycloak.KEYCLOAK_ADMIN,
        KEYCLOAK_ADMIN_PASSWORD: envSource.secretKeyRef.withName(config.secrets.keycloak.root_password_secret) + envSource.secretKeyRef.withKey("password"),
        KEYCLOAK_REALM: pim.keycloak.REALM,
        KEYCLOAK_DOMAIN_NAME: config.endpoint.SCHEME + "://" + config.endpoint.KEYCLOAK_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN,
        KEYCLOAK_PORT: std.toString(pim.ports.KEYCLOAK),
        KC_API_CLIENT_NAME: pim.keycloak.KC_API_CLIENT_NAME,
        KC_MINIO_CLIENT_NAME: pim.keycloak.KC_MINIO_CLIENT_NAME,
        KC_CKAN_CLIENT_NAME: pim.keycloak.KC_CKAN_CLIENT_NAME,
        KC_QUAY_PUSHERS: pim.registry.QUAY_PUSHERS_ROLE,
        KC_QUAY_PULLERS: pim.registry.QUAY_PULLERS_ROLE,
        KC_QUAY_GROUP_CLAIM: pim.registry.KC_ROLES_CLAIM,
        KUBE_NAMESPACE: pim.namespace,
        KC_API_CLIENT_REDIRECT: config.endpoint.SCHEME + "://" + config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN + "/*",
        KC_MINIO_CLIENT_REDIRECT: config.endpoint.SCHEME + "://" + config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN + "/s3/oauth_callback",
        KC_CKAN_CLIENT_REDIRECT: config.endpoint.SCHEME + "://" + config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN + "/*",
        KC_API_CLIENT_HOME_URL: config.endpoint.SCHEME + "://" + config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN + "/stelar",
        KC_MINIO_CLIENT_HOME_URL: config.endpoint.SCHEME + "://" + config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN + "/s3/console",
        KC_CKAN_CLIENT_HOME_URL: config.endpoint.SCHEME + "://" + config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN + "/dc",
        KC_API_CLIENT_ROOT_URL: config.endpoint.SCHEME + "://" + config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN + "/stelar",
        KC_MINIO_CLIENT_ROOT_URL: config.endpoint.SCHEME + "://" + config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN + "/s3/console",
        KC_CKAN_CLIENT_ROOT_URL: config.endpoint.SCHEME + "://" + config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN + "/dc",
    },

    manifest(pim, config): {
        kcinitjob: job.new("kcinit")
            + job.metadata.withLabels({
                'app.kubernetes.io/name': 'kc-init',
                'app.kubernetes.io/component': 'kcinit',
            })
            + job.spec.template.spec.withContainers(containers=[
                container.new("kcinit-container", pim.images.KC_INIT)
                + container.withImagePullPolicy("Always")
                + container.withEnvMap($.env(pim, config))
            ])
            + job.spec.template.spec.withInitContainers([
                podinit.wait4_postgresql("wait4-db", pim, config),
                podinit.wait4_http("wait4-keycloak", "http://keycloak:9000/health/ready"),
            ])
            + job.spec.template.spec.withServiceAccountName("sysinit")
            + job.spec.template.spec.withRestartPolicy("Never"),
    }
}
