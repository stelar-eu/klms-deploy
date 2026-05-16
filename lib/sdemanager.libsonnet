local k = import "k.libsonnet";
local svcs = import "services.libsonnet";

local deploy = k.apps.v1.deployment;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;


{
    manifest(pim,config): {

        deployment: deploy.new(name="sde-manager", containers=[
            ########################################
            ## SDE MANAGER CONTAINER ###############
            ## Listens on: 8080  ###################
            ########################################
            container.new("sdeui", pim.images.SDE_MANAGER_IMAGE)
            + container.withImagePullPolicy("Always")
            + container.withEnvMap({
                CONTEXT_PATH: "sde",
                MINIO_INSECURE: config.minio.INSECURE_MC_CLIENT,
                EMBEDDOR_DOMAIN: config.endpoint.SCHEME + "://" + config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN,
            })
            + container.withPorts([
                containerPort.newNamed(pim.ports.VISUALIZER, "sdeui"),
            ]),
        ],
        podLabels={
        'app.kubernetes.io/name': 'sdeui',
        'app.kubernetes.io/component': 'sde-manager',
        }),

        sdeui_svc: svcs.serviceFor(self.deployment),
    }

}