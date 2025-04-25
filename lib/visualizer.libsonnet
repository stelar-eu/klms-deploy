
local k = import "k.libsonnet";
local svcs = import "services.libsonnet";

local deploy = k.apps.v1.deployment;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;


{
    manifest(pim,config): {

        deployment: deploy.new(name="visualizer", containers=[
            ########################################
            ## VISUALIZER CONTAINER ################
            ## Listens on: 8080  ###################
            ########################################
            container.new("profvis", pim.images.VISUALIZER_IMAGE)
            + container.withImagePullPolicy("Always")
            + container.withEnvMap({
                CONTEXT_PATH: "visualizer",
                EMBEDDOR_DOMAIN: config.endpoint.SCHEME + "://" + config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN,
            })
            + container.withPorts([
                containerPort.newNamed(pim.ports.VISUALIZER, "vis"),
            ]),
        ],
        podLabels={
        'app.kubernetes.io/name': 'vis',
        'app.kubernetes.io/component': 'visualizer',
        }),

        vis_svc: svcs.serviceFor(self.deployment),
    }

}