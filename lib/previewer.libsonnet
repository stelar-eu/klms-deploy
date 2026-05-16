local k = import "k.libsonnet";
local svcs = import "services.libsonnet";

local deploy = k.apps.v1.deployment;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;


{
    manifest(pim,config): {

        deployment: deploy.new(name="previewer", containers=[
            ################################################
            ## Resourece Previewer CONTAINER ###############
            ## Listens on: 8080  ###########################
            ################################################
            container.new("resprev", pim.images.PREVIEWER_IMAGE)
            + container.withImagePullPolicy("Always")
            + container.withEnvMap({
                CONTEXT_PATH: "previewer",
                MINIO_INSECURE: config.minio.INSECURE_MC_CLIENT,
                EMBEDDOR_DOMAIN: config.endpoint.SCHEME + "://" + config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN,
            })
            + container.withPorts([
                containerPort.newNamed(pim.ports.VISUALIZER, "ui"),
            ]),
        ],
        podLabels={
        'app.kubernetes.io/name': 'previewer',
        'app.kubernetes.io/component': 'res-previewer',
        }),

        prev_svc: svcs.serviceFor(self.deployment),
    }

}