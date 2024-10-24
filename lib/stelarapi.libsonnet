/*
    Deployment of the STELAR API service.
 */

local podinit = import "podinit.libsonnet";
local pvol = import "pvolumes.libsonnet";
local svcs = import "services.libsonnet";
local rbac = import "rbac.libsonnet";

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


#Liveness probe urls used by wait4x during init container(s) runtime.
local CKAN_URL(pim) = "http://ckan:%s/api/3/action/status_show" % pim.ports.CKAN;

local DB_URL(pim, psm) = "postgresql://%(user)s:%(password)s@%(host)s/%(db)s?sslmode=disable" % { user: pim.db.CKAN_DB_USER, password: psm.db.CKAN_DB_PASSWORD, host: pim.db.POSTGRES_HOST, db: pim.db.STELAR_DB };

local API_CONFIG(pim, psm) = {

    ########################################
    ##  DATABASE  ##########################
    ########################################
    POSTGRES_HOST: pim.db.POSTGRES_HOST,
    POSTGRES_PORT: std.toString(pim.ports.PG),
    POSTGRES_USER: pim.db.CKAN_DB_USER,
    POSTGRES_PASSWORD: psm.db.CKAN_DB_PASSWORD,
    POSTGRES_DB: psm.db.STELAR_DB,


    ########################################
    ##  CKAN ###############################
    ########################################
    CKAN_SITE_URL: "http://ckan:%d" % pim.ports.CKAN,
    SPARQL_ENDPOINT: "http://ontop:%d/sparql" % pim.ports.ONTOP,


    ########################################
    ##  KEYCLOAK  ##########################
    ########################################
    KEYCLOAK_URL: "http://keycloak:"+std.toString(pim.ports.KEYCLOAK), #Note: Keycloak URL should contain protocol like "http://keycloak:8080"
    KEYCLOAK_CLIENT_ID: pim.api.KEYCLOAK_CLIENT_ID,
    REALM_NAME: pim.keycloak.REALM,


    ########################################
    ##  DOMAINS  ###########################
    ########################################
    # Note: Plain domains name without protocol!!!
    KLMS_DOMAIN_NAME: psm.cluster.ROOT_DOMAIN, # eg "stelar.gr"
    MAIN_INGRESS_SUBDOMAIN: psm.cluster.endpoint.PRIMARY_SUBDOMAIN, # eg "klms"
    KEYCLOAK_SUBDOMAIN: psm.cluster.endpoint.KEYCLOAK_SUBDOMAIN, # eg "kc"
    MINIO_API_SUBDOMAIN: psm.cluster.endpoint.MINIO_API_SUBDOMAIN, # eg "minio"


    ########################################
    ##  API CORE  ##########################
    ########################################
    FLASK_APPLICATION_ROOT: pim.api.FLASK_ROOT, # "/stelar"
    FLASK_RUN_PORT: std.toString(pim.ports.STELARAPI),
    API_URL: pim.api.INTERNAL_URL, # Note: this is not the actual API url, but instead it is the URL sent to tool executions as hookup!


    ########################################
    ##  SMTP  ##############################
    ########################################
    SMTP_USERNAME: psm.api.SMTP_USERNAME,
    SMTP_PASSWORD: psm.api.SMTP_PASSWORD, # 'C2g9mh$551!4'
    SMTP_SERVER: psm.api.SMTP_PASSWORD,
    SMTP_PORT: psm.api.SMTP_PORT,

    EXECUTION_ENGINE: pim.api.EXEC_ENGINE, # "kubernetes"
};

{ 
    manifest(pim, psm): {

        cmap: configMap.new("api-config-map") + 
              configMap.withData(API_CONFIG(pim, psm)),

        deployment: deploy.new(
            name="stelarapi",
            containers=[
                container.new("apiserver", psm.images.API_IMAGE)
                + container.withImagePullPolicy("Always")
                + container.withEnvFrom([{
                    configMapRef: {
                        name: "api-config-map",
                    },
                }])
                + container.withEnvMixin([
                    // Needed to configure exec engine!
                    envVar.fromFieldPath('API_NAMESPACE', 'metadata.namespace')
                ])
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
            podinit.wait4_postgresql("wait4-db", DB_URL(pim, psm)),
            podinit.wait4_http("wait4-ckan", CKAN_URL(pim)),
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