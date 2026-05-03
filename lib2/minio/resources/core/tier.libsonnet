// Core tier composition for the minio component.
local minio_configmap = import "configmap.libsonnet";
local minio_pvc = import "pvc.libsonnet";
local minio_statefulset = import "statefulset.libsonnet";
local minio_service = import "service.libsonnet";

{
  // Core tier composition for MinIO storage and service exposure.
  new(config): {
    configmap: minio_configmap.new(config),
    pvc: minio_pvc.new(),
    statefulset: minio_statefulset.new(config),
    service: minio_service.new(config),
  },
}
