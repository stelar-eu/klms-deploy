// Core StatefulSet constructor for the solr component.
local k = import "../../../util/k.libsonnet";
local pim = import "../../pim.libsonnet";
local system_pim = import "../../../system/pim.libsonnet";

local stateful = k.apps.v1.statefulSet;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;
local volumeMount = k.core.v1.volumeMount;
local vol = k.core.v1.volume;

{
  new():
    stateful.new(
      name = "solr",
      containers = [
        container.new("solr", pim.images.SOLR_IMAGE)
        + container.livenessProbe.exec.withCommand(pim.probes.liveness.command)
        + container.livenessProbe.withInitialDelaySeconds(pim.probes.liveness.initial_delay_seconds)
        + container.livenessProbe.withPeriodSeconds(pim.probes.liveness.period_seconds)
        + container.livenessProbe.withFailureThreshold(pim.probes.liveness.failure_threshold)
        + container.livenessProbe.withTimeoutSeconds(pim.probes.liveness.timeout_seconds)
        + container.readinessProbe.exec.withCommand(pim.probes.readiness.command)
        + container.readinessProbe.withInitialDelaySeconds(pim.probes.readiness.initial_delay_seconds)
        + container.readinessProbe.withPeriodSeconds(pim.probes.readiness.period_seconds)
        + container.readinessProbe.withTimeoutSeconds(pim.probes.readiness.timeout_seconds)
        + container.readinessProbe.withFailureThreshold(pim.probes.readiness.failure_threshold)
        + container.readinessProbe.withSuccessThreshold(pim.probes.readiness.success_threshold)
        + container.withPorts([
          containerPort.newNamed(system_pim.ports.SOLR, pim.service.port_name),
        ])
        + container.withVolumeMounts([
          volumeMount.new(pim.pvc.volume_name, pim.pvc.mount_path, false),
        ])
        + container.securityContext.withAllowPrivilegeEscalation(pim.security.allow_privilege_escalation),
      ],
      podLabels = pim.labels
    )
    + stateful.spec.template.spec.withVolumes([
      vol.fromPersistentVolumeClaim(pim.pvc.volume_name, pim.pvc.name),
    ])
    + stateful.spec.template.spec.securityContext.withFsGroup(pim.security.fs_group),
}
