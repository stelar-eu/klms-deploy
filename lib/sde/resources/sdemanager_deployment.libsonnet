// Core Deployment constructor for the SDE Manager UI inside the sde component.
local k = import "../../util/k.libsonnet";

local deploy = k.apps.v1.deployment;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;

{
  new(config):
    deploy.new(
      name = config.sdemanager.deployment_name,
      containers = [
        container.new(config.sdemanager.container_name, config.images.SDE_MANAGER_IMAGE)
        + container.withImagePullPolicy(config.sdemanager.image_pull_policy)
        + container.withEnvMap({
          CONTEXT_PATH: config.sdemanager.context_path,
          MINIO_INSECURE: config.minio.INSECURE_MC_CLIENT,
          EMBEDDOR_DOMAIN: config.endpoint.SCHEME + "://" + config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN,
        })
        + container.withPorts([
          containerPort.newNamed(config.sdemanager.port, config.sdemanager.port_name),
        ]),
      ],
      podLabels = config.sdemanager.labels
    ),
}
