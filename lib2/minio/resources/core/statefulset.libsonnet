// Core StatefulSet constructor for the minio component.
local k = import "../../../util/k.libsonnet";
local pim = import "../../pim.libsonnet";

local container = k.core.v1.container;
local stateful = k.apps.v1.statefulSet;
local containerPort = k.core.v1.containerPort;
local volumeMount = k.core.v1.volumeMount;
local vol = k.core.v1.volume;
local envSource = k.core.v1.envVarSource;

{
  new(config):
    stateful.new(name = "minio", containers = [
      container.new("minio", pim.images.MINIO_IMAGE)
      + container.withImagePullPolicy(pim.deployment.image_pull_policy)
      + container.withEnvMap({
        MINIO_ROOT_PASSWORD: envSource.secretKeyRef.withName(config.secrets.minio.minio_root_password_secret) + envSource.secretKeyRef.withKey("password"),
      })
      + container.withEnvFrom([{
        configMapRef: {
          name: "minio-cmap",
        },
      }])
      + container.withPorts([
        containerPort.newNamed(pim.ports.MINIO, "minio"),
        containerPort.newNamed(pim.ports.MINIOAPI, "minapi"),
      ])
      + container.withCommand(["minio", "server", "/data", "--console-address", ":" + std.toString(pim.ports.MINIO)])
      + container.withVolumeMounts([
        volumeMount.new(pim.pvc.volume_name, pim.pvc.mount_path, false),
      ]),
    ], podLabels = pim.labels)
    + stateful.spec.template.spec.withVolumes([
      vol.fromPersistentVolumeClaim(pim.pvc.volume_name, pim.pvc.name),
    ]),
}
