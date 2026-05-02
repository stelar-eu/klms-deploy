local k = import "../../../util/k.libsonnet";
local pim = import "../../pim.libsonnet";

local deploy = k.apps.v1.deployment;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;

{
  new():
    deploy.new(
      name = "redis",
      containers = [
        container.new("redis", pim.images.REDIS_IMAGE)
        + container.livenessProbe.exec.withCommand(pim.probes.liveness.command)
        + container.livenessProbe.withInitialDelaySeconds(pim.probes.liveness.initial_delay_seconds)
        + container.livenessProbe.withPeriodSeconds(pim.probes.liveness.period_seconds)
        + container.readinessProbe.exec.withCommand(pim.probes.readiness.command)
        + container.readinessProbe.withInitialDelaySeconds(pim.probes.readiness.initial_delay_seconds)
        + container.readinessProbe.withPeriodSeconds(pim.probes.readiness.period_seconds)
        + container.withPorts([
          containerPort.newNamed(pim.ports.REDIS, "redis"),
        ]),
      ],
      podLabels = pim.labels
    ),
}
