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

        initjob: job.new("sysinit")
            + job.metadata.withLabels({
                'app.kubernetes.io/name': 'stelar-init',
                'app.kubernetes.io/component': 'stelarinit',
            })
            + job.spec.template.spec.withContainers(containers=[
                container.new("stelarinitContainer", pim.images.SYSTEM_INIT)
                + container.withEnvMap({
                    A_CKAN_DB_PASSWORD: envSource.secretKeyRef.withName(config.secrets.db.ckan_db_password_secret)+envSource.secretKeyRef.withKey("password"),
                    KEYCLOAK_ADMIN_PASSWORD: envSource.secretKeyRef.withName(config.secrets.keycloak.root_password_secret)+envSource.secretKeyRef.withKey("password"),
                    CKAN_SYSADMIN_PASSWORD: envSource.secretKeyRef.withName(config.secrets.ckan.ckan_admin_password_secret)+envSource.secretKeyRef.withKey("password"),
                    
                    CKAN_SYSADMIN_EMAIL: "",
                    CKAN_SYSADMIN_NAME: "",
                    CKAN_SITE_URL: config.endpoint.SCHEME+"://"+config.endpoint.PRIMARY_SUBDOMAIN+"."+config.endpoint.ROOT_DOMAIN,
                    CKAN_SQLALCHEMY_URL: "",
                    KEYCLOAK_ADMIN_USER: "", 
                })
            ])
            + job.spec.template.spec.withInitContainers([
                podinit.wait4_postgresql("wait4-db", pim, config),
                podinit.wait4_http("wait4-keycloak", "http://keycloak:9000/health/ready"),
            ])
            + job.spec.template.spec.withServiceAccountName("sysinit")
            + job.spec.template.spec.withRestartPolicy("never"),

        initrbac: rbac.namespacedRBAC("sysinit", [
            rbac.resourceRule(
                ["create","get","list","update","delete"],
                [""],
                ["secrets","configmaps"])
        ]),
    }

}