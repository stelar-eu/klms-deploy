local minio_configmap = import "configmap.libsonnet";
local minio_pvc = import "pvc.libsonnet";
local minio_statefulset = import "statefulset.libsonnet";
local minio_service = import "service.libsonnet";

{
  new(config): {
    configmap: minio_configmap.new(config),
    pvc: minio_pvc.new(),
    statefulset: minio_statefulset.new(config),
    service: minio_service.new(config),
  },
}
