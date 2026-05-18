// Core Deployment constructor for the visualizer component.
local k = import "../../util/k.libsonnet";

local deploy = k.apps.v1.deployment;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;

{
  new(config):
    deploy.new(
      name = config.deployment.name,
      containers = [
        container.new(config.deployment.container_name, config.images.VISUALIZER_IMAGE)
        + container.withImagePullPolicy(config.deployment.image_pull_policy)
        + container.withEnvMap({
          CONTEXT_PATH: config.app.CONTEXT_PATH,
          MINIO_INSECURE: config.minio.INSECURE_MC_CLIENT,
          EMBEDDOR_DOMAIN: config.endpoint.SCHEME + "://" + config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN,
        })
        + container.withPorts([
          containerPort.newNamed(config.ports.VISUALIZER, config.service.port_name),
        ]),
      ],
      podLabels = config.labels
    ),
}
