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

// Configuration Imports
local IMAGE_CONFIG = import "images.jsonnet";
local APICONFIG = import 'apiconfig.jsonnet';

{ 
    manifest(psm): {

        cmap: configMap.new("api-config-map") + 
              configMap.withData(APICONFIG.API_ENV),

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
                    containerPort.newNamed(APICONFIG.API_PORT, "api")
                ])

            ],
            podLabels={
                'app.kubernetes.io/name': 'stelar-api',
                'app.kubernetes.io/component': 'stelarapi',
            }
        )

        + deploy.spec.template.spec.withInitContainers([
            /* We need to wait for ckan to be ready */
            podinit.wait4_postgresql("wait4-db", APICONFIG.DB_URL),
            podinit.wait4_http("wait4-ckan", APICONFIG.CKAN_URL),
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