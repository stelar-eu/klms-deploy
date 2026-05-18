// Core Deployment constructor for the registry component.
local k = import "../../util/k.libsonnet";
local podinit = import "../../util/podinit.libsonnet";

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
        container.new("quay", config.quay.IMAGE)
        + container.withImagePullPolicy("Always")
        + container.withPorts([
          containerPort.newNamed(config.quay.PORT, "quay"),
        ])
        + container.withVolumeMounts([
          volumeMount.new("quay-conf", "/quay-registry/conf/stack", false),
        ]),
      ],
      podLabels = {
        "app.kubernetes.io/name": "quay",
        "app.kubernetes.io/component": "quay",
      }
    )
    + deploy.spec.template.spec.withInitContainers([
      podinit.wait4_postgresql("wait4-db", config),
      podinit.wait4_http("wait4-keycloak", "http://keycloak:9000/health/ready"),
    ])
    + deploy.spec.template.spec.withVolumes([
      vol.fromConfigMap("quay-conf", "registry-config", [{ key: "config.yaml", path: "config.yaml" }]),
    ])
}
