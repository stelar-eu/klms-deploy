// Stable root entrypoint for the minio component.
local minio_configmap = import "resources/configmap.libsonnet";
local minio_pvc = import "resources/pvc.libsonnet";
local minio_statefulset = import "resources/statefulset.libsonnet";
local minio_service = import "resources/service.libsonnet";
local minio_ingress = import "resources/ingress.libsonnet";

{
  // Root component entrypoint: directly mount all MinIO-owned resources.
  manifest(config): {
    configmap: minio_configmap.new(config),
    pvc: minio_pvc.new(config),
    statefulset: minio_statefulset.new(config),
    service: minio_service.new(config),
    ingress: minio_ingress.new(config),
  },
}
