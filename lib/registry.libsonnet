
local k = import "k.libsonnet";
local pvol = import "pvolumes.libsonnet";
local svcs = import "services.libsonnet";
local PORT = import "stdports.libsonnet";

local deploy = k.apps.v1.deployment;
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
local podinit = import "podinit.libsonnet";
local envSource = k.core.v1.envVarSource;


{
    manifest(pim,config): {
        
        ########################################
        ##  QUAY IMAGE REGISTRY  ###############
        ########################################
        deployment: deploy.new(name="quay", containers=[
            container.new("quay", pim.images.REGISTRY_IMAGE)
            + container.withImagePullPolicy("Always")
            + container.withPorts([
                containerPort.newNamed(pim.ports.QUAY, "quay"),
            ])
            + container.withVolumeMounts([
                volumeMount.new("quay-conf","/quay-registry/conf/stack", false),
            ])
        ],
        podLabels={
            'app.kubernetes.io/name': 'quay',
            'app.kubernetes.io/component': 'quay',
        })
        + deploy.spec.template.spec.withInitContainers([
            /* We need to wait for Keycloak and DB to be ready */
            podinit.wait4_postgresql("wait4-db", pim, config),
            podinit.wait4_http("wait4-keycloak", "http://keycloak:9000/health/ready"),
        ])
        + deploy.spec.template.spec.withVolumes([
            vol.fromConfigMap('quay-conf','registry-config', [{key:'config.yaml', path:'config.yaml'}])
        ]),

        quay_svc: svcs.serviceFor(self.deployment),

    }
}