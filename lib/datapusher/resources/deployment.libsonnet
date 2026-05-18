// Core Deployment constructor for the datapusher component.
local k = import "../../util/k.libsonnet";

local deploy = k.apps.v1.deployment;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;

{
  new(config):
    deploy.new(
      name = "datapusher",
      containers = [
        container.new("datapusher", "ckan/ckan-base-datapusher:%s" % config.datapusher.DATAPUSHER_VERSION)
        + container.livenessProbe.exec.withCommand(["/usr/bin/wget", "-qO", "/dev/null", "http://127.0.0.1:8800"])
        + container.livenessProbe.withInitialDelaySeconds(30)
        + container.livenessProbe.withPeriodSeconds(15)
        + container.livenessProbe.withTimeoutSeconds(10)
        + container.livenessProbe.withFailureThreshold(5)
        + container.readinessProbe.httpGet.withPort(config.datapusher.PORT)
        + container.readinessProbe.withInitialDelaySeconds(15)
        + container.readinessProbe.withPeriodSeconds(15)
        + container.readinessProbe.withTimeoutSeconds(10)
        + container.readinessProbe.withFailureThreshold(5)
        + container.readinessProbe.withSuccessThreshold(1)
        + container.withPorts([
          containerPort.newNamed(config.datapusher.PORT, "datapusher"),
        ]),
      ],
      podLabels = {
        "app.kubernetes.io/name": "data-catalog",
        "app.kubernetes.io/component": "datapusher",
      }
    )
}
