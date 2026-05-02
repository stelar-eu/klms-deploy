local minio_configmap = import "resources/core/configmap.libsonnet";
local minio_pvc = import "resources/core/pvc.libsonnet";
local minio_statefulset = import "resources/core/statefulset.libsonnet";
local minio_service = import "resources/core/service.libsonnet";

{
  manifest(config): {
    configmap: minio_configmap.new(config),
    pvc: minio_pvc.new(),
    statefulset: minio_statefulset.new(config),
    service: minio_service.new(config),
  },
}
