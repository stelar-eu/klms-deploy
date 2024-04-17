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

local DBENV = import "dbenv.jsonnet";
local PORT = import "stdports.libsonnet";
local IMAGE_NAME = "vsam/stelar-okeanos:stelarapi";


local db_url = "postgresql://%(user)s:%(password)s@%(host)s/%(db)s?sslmode=disable" % {
    user: DBENV.CKAN_DB_USER,
    password: DBENV.CKAN_DB_PASSWORD,
    host: "db",
    db: DBENV.CKAN_DB
};

local ckan_url = "http://ckan:%s/api/3/action/status_show" % PORT.CKAN;

local ENV = {
    POSTGRES_HOST: 'db',
    POSTGRES_PORT: std.toString(PORT.PG),
    POSTGRES_USER: DBENV.CKAN_DB_USER,
    POSTGRES_PASSWORD: DBENV.CKAN_DB_PASSWORD,
    POSTGRES_DB: DBENV.CKAN_DB,

    SERVICE_PORT: std.toString(PORT.STELARAPI),
    CKAN_SITE_URL: "http://ckan:%d" % PORT.CKAN,
    SPARQL_ENDPOINT: "http://ontop:%d/sparql" % PORT.ONTOP,

    FLASK_APPLICATION_ROOT: "/stelar",

    // Note: this is not the actual API url, but instead it is the
    // URL sent to tool executions as hookup!
    API_URL: "http://stelarapi/",

    // duh!
    EXECUTION_ENGINE: "kubernetes",
};


{ 
    manifest(psm): {

        deployment: deploy.new(
            name="stelarapi",
            containers=[
                container.new("apiserver", IMAGE_NAME)
                + container.withImagePullPolicy("Always")
                + container.withEnvMap(ENV)
                + container.withEnvMixin([
                    // Needed to configure exec engine!
                    envVar.fromFieldPath('API_NAMESPACE', 'metadata.namespace')
                ])
                + container.withPorts([
                    containerPort.newNamed(PORT.STELARAPI, "api")
                ])

                /* TODO: Add liveness and readiness probes */

            ],
            podLabels={
                'app.kubernetes.io/name': 'stelar-api',
                'app.kubernetes.io/component': 'stelarapi',
            }
        )

        + deploy.spec.template.spec.withInitContainers([
            /* We need to wait for ckan to be ready */
            podinit.wait4_postgresql("wait4-db", db_url),
            podinit.wait4_http("wait4-ckan", ckan_url),
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