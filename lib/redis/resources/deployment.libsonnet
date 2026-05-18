// Core Deployment constructor for the redis component.
local k = import "../../util/k.libsonnet";

local deploy = k.apps.v1.deployment;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;

{
  new(config):
    deploy.new(
      name = "redis",
      containers = [
        container.new("redis", config.redis.IMAGE)
        + container.livenessProbe.exec.withCommand(["/usr/local/bin/redis-cli", "-e", "QUIT"])
        + container.livenessProbe.withInitialDelaySeconds(30)
        + container.livenessProbe.withPeriodSeconds(10)
        + container.readinessProbe.exec.withCommand(["/usr/local/bin/redis-cli", "-e", "QUIT"])
        + container.readinessProbe.withInitialDelaySeconds(30)
        + container.readinessProbe.withPeriodSeconds(10)
        + container.withPorts([
          containerPort.newNamed(config.redis.PORT, "redis"),
        ]),
      ],
      podLabels = {
        "app.kubernetes.io/name": "data-catalog",
        "app.kubernetes.io/component": "redis",
      }
    )
}
