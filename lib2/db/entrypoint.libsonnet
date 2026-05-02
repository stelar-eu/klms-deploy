local db_pvc = import "resources/core/pvc.libsonnet";
local db_statefulset = import "resources/core/statefulset.libsonnet";
local db_service = import "resources/core/service.libsonnet";

{
  manifest(config): {
    pvc: db_pvc.new(),
    statefulset: db_statefulset.new(config),
    service: db_service.new(),
  },
}
