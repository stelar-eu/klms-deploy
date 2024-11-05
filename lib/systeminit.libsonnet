local k = import "k.libsonnet";
local podinit = import "podinit.libsonnet";
local rbac = import "rbac.libsonnet";

local deploy = k.apps.v1.deployment;
local job = k.batch.v1.job;
local container = k.core.v1.container;
local stateful = k.apps.v1.statefulSet;
local containerPort = k.core.v1.containerPort;
local pod = k.core.v1.pod;
local port = k.core.v1.containerPort;
local volumeMount = k.core.v1.volumeMount;
local vol = k.core.v1.volume;
local cmap = k.core.v1.configMap;
local service = k.core.v1.service;
local secret = k.core.v1.secret;
local envSource = k.core.v1.envVarSource;


{
    manifest(pim,config): {

        kcinitjob: job.new("kcinit")
            + job.metadata.withLabels({
                'app.kubernetes.io/name': 'kc-init',
                'app.kubernetes.io/component': 'kcinit',
            })
            + job.spec.template.spec.withContainers(containers=[
                container.new("kcinitContainer", pim.images.KC_INIT)
                + container.withEnvMap({
                    KEYCLOAK_ADMIN : pim.keycloak.KEYCLOAK_ADMIN,
                    KEYCLOAK_ADMIN_PASSWORD : envSource.secretKeyRef.withName(config.secrets.keycloak.root_password_secret)+envSource.secretKeyRef.withKey("password"),
                    KEYCLOAK_REALM: pim.keycloak.REALM,
                    KEYCLOAK_PORT: pim.ports.KEYCLOAK,
                    KC_API_CLIENT_NAME: pim.keycloak.KC_API_CLIENT_NAME,
                    KC_MINIO_CLIENT_NAME: pim.keycloak.KC_MINIO_CLIENT_NAME,
                    KC_CKAN_CLIENT_NAME: pim.keycloak.KC_CKAN_CLIENT_NAME,
                    KUBE_NAMESPACE: pim.namespace,
                    KC_API_CLIENT_REDIRECT: config.endpoint.SCHEME+"://"+config.endpoint.PRIMARY_SUBDOMAIN+"."+config.endpoint.ROOT_DOMAIN+"/*",
                    KC_MINIO_CLIENT_REDIRECT: config.endpoint.SCHEME+"://"+config.endpoint.PRIMARY_SUBDOMAIN+"."+config.endpoint.ROOT_DOMAIN+"/*",
                    KC_CKAN_CLIENT_REDIRECT: config.endpoint.SCHEME+"://"+config.endpoint.PRIMARY_SUBDOMAIN+"."+config.endpoint.ROOT_DOMAIN+"/*",
                    KC_API_CLIENT_HOME_URL: config.endpoint.SCHEME+"://"+config.endpoint.PRIMARY_SUBDOMAIN+"."+config.endpoint.ROOT_DOMAIN+"/stelar",
                    KC_MINIO_CLIENT_HOME_URL:config.endpoint.SCHEME+"://"+config.endpoint.PRIMARY_SUBDOMAIN+"."+config.endpoint.ROOT_DOMAIN+"/s3/console",
                    KC_CKAN_CLIENT_HOME_URL: config.endpoint.SCHEME+"://"+config.endpoint.PRIMARY_SUBDOMAIN+"."+config.endpoint.ROOT_DOMAIN+"/dc",
                    KC_API_CLIENT_ROOT_URL: config.endpoint.SCHEME+"://"+config.endpoint.PRIMARY_SUBDOMAIN+"."+config.endpoint.ROOT_DOMAIN+"/stelar",
                    KC_MINIO_CLIENT_ROOT_URL: config.endpoint.SCHEME+"://"+config.endpoint.PRIMARY_SUBDOMAIN+"."+config.endpoint.ROOT_DOMAIN+"/s3/console",
                    KC_CKAN_CLIENT_ROOT_URL: config.endpoint.SCHEME+"://"+config.endpoint.PRIMARY_SUBDOMAIN+"."+config.endpoint.ROOT_DOMAIN+"/dc",
                })
            ])
            + job.spec.template.spec.withInitContainers([
                podinit.wait4_postgresql("wait4-db", pim, config),
                podinit.wait4_http("wait4-keycloak", "http://keycloak:9000/health/ready"),
            ])
            + job.spec.template.spec.withServiceAccountName("kcinit")
            + job.spec.template.spec.withRestartPolicy("never"),

        kcinitrbac: rbac.namespacedRBAC("kcinit", [
            rbac.resourceRule(
                ["create","get","list","update","delete"],
                [""],
                ["secrets","configmaps"])
        ]),



        ckaninitjob:job.new("ckaninit")
            + job.metadata.withLabels({
                'app.kubernetes.io/name': 'ckan-init',
                'app.kubernetes.io/component': 'ckaninit',
            })
            + job.spec.template.spec.withContainers(containers=[
                container.new("ckaninitContainer", pim.images.KC_INIT)
                + container.withEnvMap({
                    
                })
            ])
            + job.spec.template.spec.withInitContainers([
                podinit.wait4_postgresql("wait4-db", pim, config),
                // podinit.wait4_http("wait4-keycloak", "http://keycloak:9000/health/ready"),
            ])
            + job.spec.template.spec.withServiceAccountName("ckaninit")
            + job.spec.template.spec.withRestartPolicy("never"),

        
    }

}