// Core StatefulSet constructor for the solr component.
local k = import "../../util/k.libsonnet";

local stateful = k.apps.v1.statefulSet;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;
local volumeMount = k.core.v1.volumeMount;
local vol = k.core.v1.volume;

{
  new(config):
    stateful.new(
      name = "solr",
      containers = [
        container.new("solr", "ckan/ckan-solr:%s" % config.solr.SOLR_IMAGE_VERSION)
        + container.livenessProbe.exec.withCommand(["/usr/bin/wget", "-qO", "/dev/null", "http://127.0.0.1:8983/solr/"])
        + container.livenessProbe.withInitialDelaySeconds(120)
        + container.livenessProbe.withPeriodSeconds(20)
        + container.livenessProbe.withFailureThreshold(3)
        + container.livenessProbe.withTimeoutSeconds(45)
        + container.readinessProbe.exec.withCommand(["/usr/bin/curl", "http://127.0.0.1:8983/solr/"])
        + container.readinessProbe.withInitialDelaySeconds(120)
        + container.readinessProbe.withPeriodSeconds(20)
        + container.readinessProbe.withTimeoutSeconds(45)
        + container.readinessProbe.withFailureThreshold(5)
        + container.readinessProbe.withSuccessThreshold(1)
        + container.withPorts([
          containerPort.newNamed(config.solr.PORT, "solr"),
        ])
        + container.withVolumeMounts([
          volumeMount.new("solr-storage-vol", "/var/solr", false),
        ])
        + container.securityContext.withAllowPrivilegeEscalation(false),
      ],
      podLabels = {
        "app.kubernetes.io/name": "data-catalog",
        "app.kubernetes.io/component": "solr",
      }
    )
    + stateful.spec.template.spec.withVolumes([
      vol.fromPersistentVolumeClaim("solr-storage-vol", "solr-data"),
    ])
    + stateful.spec.template.spec.securityContext.withFsGroup(8983)
}
