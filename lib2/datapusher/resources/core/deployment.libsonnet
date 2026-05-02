local k = import "../../../util/k.libsonnet";
local pim = import "../../pim.libsonnet";

local deploy = k.apps.v1.deployment;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;

{
  new():
    deploy.new(
      name = "datapusher",
      containers = [
        container.new("datapusher", pim.images.DATAPUSHER_IMAGE)
        + container.livenessProbe.exec.withCommand(pim.probes.liveness.command)
        + container.livenessProbe.withInitialDelaySeconds(pim.probes.liveness.initial_delay_seconds)
        + container.livenessProbe.withPeriodSeconds(pim.probes.liveness.period_seconds)
        + container.livenessProbe.withTimeoutSeconds(pim.probes.liveness.timeout_seconds)
        + container.livenessProbe.withFailureThreshold(pim.probes.liveness.failure_threshold)
        + container.readinessProbe.httpGet.withPort(pim.probes.readiness.port)
        + container.readinessProbe.withInitialDelaySeconds(pim.probes.readiness.initial_delay_seconds)
        + container.readinessProbe.withPeriodSeconds(pim.probes.readiness.period_seconds)
        + container.readinessProbe.withTimeoutSeconds(pim.probes.readiness.timeout_seconds)
        + container.readinessProbe.withFailureThreshold(pim.probes.readiness.failure_threshold)
        + container.readinessProbe.withSuccessThreshold(pim.probes.readiness.success_threshold)
        + container.withPorts([
          containerPort.newNamed(pim.ports.DATAPUSHER, "datapusher"),
        ]),
      ],
      podLabels = pim.labels
    ),
}
