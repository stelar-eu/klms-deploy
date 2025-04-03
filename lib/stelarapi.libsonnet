/*
    Deployment of the STELAR API service.
 */

local podinit = import "podinit.libsonnet";
local pvol = import "pvolumes.libsonnet";
local svcs = import "services.libsonnet";
local rbac = import "rbac.libsonnet";
local images = import "images.libsonnet";

/* K8S API MODEL */
local k = import "k.libsonnet";

local deploy = k.apps.v1.deployment;
local stateful = k.apps.v1.statefulSet;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;
local servicePort = k.core.v1.servicePort;
local volumeMount = k.core.v1.volumeMount;
local pod = k.core.v1.pod;
local vol = k.core.v1.volume;
local service = k.core.v1.service;
local cm = k.core.v1.configMap;
local secret = k.core.v1.secret;
local envVar = k.core.v1.envVar;
local envVarSource = k.core.v1.envVarSource;
local policyRule = k.rbac.v1.policyRule;
local configMap = k.core.v1.configMap;
local envSource = k.core.v1.envVarSource;
local secretSelector = k.core.v1.secretKeySelectors;



#Liveness probe urls used by wait4x during init container(s) runtime.
local CKAN_URL(pim) = "http://ckan:%s/api/3/action/status_show" % pim.ports.CKAN;

#local DB_URL(pim, config) = "postgresql://%(user)s:%(password)s@%(host)s/%(db)s?sslmode=disable" % { user: pim.db.CKAN_DB_USER, password: secretSelector.withName(config.secrets.db.ckan_db_password_secret).withKey("password"), host: pim.db.POSTGRES_HOST, db: pim.db.STELAR_DB };

local API_CONFIG(pim, config) = {

    ########################################
    ##  DATABASE  ##########################
    ########################################
    POSTGRES_HOST: pim.db.POSTGRES_HOST,
    POSTGRES_PORT: std.toString(pim.ports.PG),
    POSTGRES_USER: pim.db.CKAN_DB_USER,
    POSTGRES_DB: pim.db.STELAR_DB,


    ########################################
    ##  CKAN ###############################
    ########################################
    CKAN_SITE_URL: "http://ckan:%d" % pim.ports.CKAN,
    SPARQL_ENDPOINT: "http://ontop:%d/sparql" % pim.ports.ONTOP,

    ########################################
    ##  KEYCLOAK  ##########################
    ########################################
    KEYCLOAK_URL: "http://keycloak:"+std.toString(pim.ports.KEYCLOAK), #Note: Keycloak URL should contain protocol like "http://keycloak:8080"
    KEYCLOAK_CLIENT_ID: pim.keycloak.KC_API_CLIENT_NAME,
    REALM_NAME: pim.keycloak.REALM,


    ########################################
    ##  DOMAINS  ###########################
    ########################################
    # Note: Plain domains name without protocol!!!
    KLMS_DOMAIN_NAME: config.endpoint.ROOT_DOMAIN, # eg "stelar.gr"
    MAIN_INGRESS_SUBDOMAIN: config.endpoint.PRIMARY_SUBDOMAIN, # eg "klms"
    KEYCLOAK_SUBDOMAIN: config.endpoint.KEYCLOAK_SUBDOMAIN, # eg "kc"
    MINIO_API_SUBDOMAIN: config.endpoint.MINIO_API_SUBDOMAIN, # eg "minio"

    MINIO_API_EXT_URL: "%(SCHEME)s://%(MINIO_API_SUBDOMAIN)s.%(ROOT_DOMAIN)s" % config.endpoint,
    KEYCLOAK_EXT_URL: "%(SCHEME)s://%(KEYCLOAK_SUBDOMAIN)s.%(ROOT_DOMAIN)s" % config.endpoint,
    KEYCLOAK_ISSUER_URL: self.KEYCLOAK_EXT_URL + "/realms/" + pim.keycloak.REALM,
    MAIN_EXT_URL: "%(SCHEME)s://%(PRIMARY_SUBDOMAIN)s.%(ROOT_DOMAIN)s" % config.endpoint,


    ########################################
    ##  MINIO  #############################
    ########################################
    MINIO_DOMAIN: config.minio.API_DOMAIN,
    MINIO_ROOT_USER: pim.minio.MINIO_ROOT_USER,
    MINIO_CONSOLE_URL: config.api.S3_CONSOLE_URL,
    MC_INSECURE: config.minio.INSECURE_MC_CLIENT,

    ########################################
    ##  API CORE  ##########################
    ########################################
    FLASK_APPLICATION_ROOT: pim.api.FLASK_ROOT, # "/stelar"
    FLASK_RUN_PORT: std.toString(pim.ports.STELARAPI),
    API_URL: pim.api.INTERNAL_URL, # Note: this is not the actual API url, but instead it is the URL sent to tool executions as hookup!


    ########################################
    ##  SMTP  ##############################
    ########################################
    SMTP_USERNAME: config.api.SMTP_USERNAME,
    SMTP_SERVER: config.api.SMTP_SERVER,
    SMTP_PORT: config.api.SMTP_PORT,

    EXECUTION_ENGINE: pim.api.EXEC_ENGINE, # "kubernetes"
};

{ 
    manifest(pim, config): {

        cmap: configMap.new("api-config-map") + 
              configMap.withData(API_CONFIG(pim, config)),

        deployment: deploy.new(
            name="stelarapi",
            containers=[

                local image = images.image_name(pim.images.API_IMAGE);
                local pull_policy = images.pull_policy(pim.images.API_IMAGE);

                container.new("apiserver", image )
                + container.withImagePullPolicy(pull_policy)
                + container.withEnvFrom([{
                    configMapRef: {
                        name: "api-config-map",
                    },
                }])
                + container.withEnvMixin([
                    // Needed to configure exec engine!
                    envVar.fromFieldPath('API_NAMESPACE', 'metadata.namespace')
                ])
                + container.withEnvMap({
                    SMTP_PASSWORD: envSource.secretKeyRef.withName(config.secrets.api.smtp_password_secret)+envSource.secretKeyRef.withKey("password"),
                    POSTGRES_PASSWORD: envSource.secretKeyRef.withName(config.secrets.db.ckan_db_password_secret)+envSource.secretKeyRef.withKey("password"),
                    KEYCLOAK_CLIENT_SECRET: envSource.secretKeyRef.withName(pim.keycloak.KC_API_CLIENT_NAME+"-client-secret")+envSource.secretKeyRef.withKey("secret"),
                    MINIO_ROOT_PASSWORD: envSource.secretKeyRef.withName(config.secrets.minio.minio_root_password_secret)+envSource.secretKeyRef.withKey("password"),
                    CKAN_ADMIN_TOKEN: envSource.secretKeyRef.withName("ckan-admin-token-secret")+envSource.secretKeyRef.withKey("token"),
                    SESSION_SECRET_KEY: envSource.secretKeyRef.withName(config.secrets.api.session_secret_key)+envSource.secretKeyRef.withKey("key"),
                    CKAN_ENCODE_KEY: envSource.secretKeyRef.withName(config.secrets.ckan.ckan_auth_secret)+envSource.secretKeyRef.withKey("jwt-key"),
                })
                + container.withPorts([
                    containerPort.newNamed(pim.ports.STELARAPI, "api")
                ])

            ],
            podLabels={
                'app.kubernetes.io/name': 'stelar-api',
                'app.kubernetes.io/component': 'stelarapi',
            }
        )

        + deploy.spec.template.spec.withInitContainers([
            /* We need to wait for ckan to be ready */
            podinit.wait4_postgresql("wait4-db", pim, config),
            podinit.wait4_http("wait4-ckan", CKAN_URL(pim)),
            podinit.wait4_http("wait4-keycloak", "http://keycloak:9000/health/ready"),
        ])
        + deploy.spec.template.spec.withServiceAccountName("stelarapi")
        ,

        svc: svcs.serviceFor(self.deployment),

        // This is needed to allow the executor to create jobs
        rbac: rbac.namespacedRBAC("stelarapi", [
            rbac.resourceRule(
                ["get", "list", "watch"], 
                [""], 
                ["*"])
                ,
            rbac.resourceRule(
                ["create", "delete", "deletecollection", "get", "list", "patch", "update", "watch"],
                ["batch"],
                ["jobs"]
            )
        ])
    }
    
}