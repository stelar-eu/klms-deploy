local k = import "../../../util/k.libsonnet";
local pim = import "../../pim.libsonnet";
local system_pim = import "../../../system/pim.libsonnet";
local podinit = import "../../../util/podinit.libsonnet";

local deploy = k.apps.v1.deployment;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;
local volumeMount = k.core.v1.volumeMount;
local vol = k.core.v1.volume;

{
  new(config):
    deploy.new(
      name = "quay",
      containers = [
        container.new("quay", pim.images.REGISTRY_IMAGE)
        + container.withImagePullPolicy(pim.deployment.image_pull_policy)
        + container.withPorts([
          containerPort.newNamed(pim.ports.QUAY, "quay"),
        ])
        + container.withVolumeMounts([
          volumeMount.new(pim.config_volume.name, pim.config_volume.mount_path, false),
        ]),
      ],
      podLabels = pim.labels
    )
    + deploy.spec.template.spec.withInitContainers([
      podinit.wait4_postgresql("wait4-db", system_pim, config),
      podinit.wait4_http("wait4-keycloak", "http://keycloak:9000/health/ready"),
    ])
    + deploy.spec.template.spec.withVolumes([
      vol.fromConfigMap(pim.config_volume.name, pim.config_volume.config_map_name, pim.config_volume.items),
    ]),
}
