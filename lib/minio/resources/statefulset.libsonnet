// Core StatefulSet constructor for the minio component.
local k = import "../../util/k.libsonnet";

local container = k.core.v1.container;
local stateful = k.apps.v1.statefulSet;
local containerPort = k.core.v1.containerPort;
local volumeMount = k.core.v1.volumeMount;
local vol = k.core.v1.volume;
local envSource = k.core.v1.envVarSource;

{
  new(config):
    stateful.new(name = "minio", containers = [
      container.new("minio", config.minio.IMAGE)
      + container.withImagePullPolicy("Always")
      + container.withEnvMap({
        MINIO_ROOT_PASSWORD: envSource.secretKeyRef.withName(config.minio.MINIO_ROOT_PASSWORD_SECRET_NAME) + envSource.secretKeyRef.withKey("password"),
      })
      + container.withEnvFrom([{
        configMapRef: {
          name: "minio-cmap",
        },
      }])
      + container.withPorts([
        containerPort.newNamed(config.minio.CONSOLE_PORT, "minio"),
        containerPort.newNamed(config.minio.API_PORT, "minapi"),
      ])
      + container.withCommand(["minio", "server", "/data", "--console-address", ":" + std.toString(config.minio.CONSOLE_PORT)])
      + container.withVolumeMounts([
        volumeMount.new("minio-storage-vol", "/data", false),
      ]),
    ], podLabels = {
      "app.kubernetes.io/name": "object-storage",
      "app.kubernetes.io/component": "minio",
    })
    + stateful.spec.template.spec.withVolumes([
      vol.fromPersistentVolumeClaim("minio-storage-vol", "minio-storage"),
    ])
}
