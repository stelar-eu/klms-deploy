// Stable root entrypoint for the minio component.
local minio_configmap = import "resources/configmap.libsonnet";
local minio_pvc = import "resources/pvc.libsonnet";
local minio_statefulset = import "resources/statefulset.libsonnet";
local minio_service = import "resources/service.libsonnet";

{
  // Root component entrypoint: directly mount all MinIO-owned resources.
  manifest(psm): {
    configmap: minio_configmap.new(psm),
    pvc: minio_pvc.new(psm),
    statefulset: minio_statefulset.new(psm),
    service: minio_service.new(psm),
  },
}
