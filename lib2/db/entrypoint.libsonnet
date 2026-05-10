// Stable root entrypoint for the db component.
local db_pvc = import "resources/pvc.libsonnet";
local db_statefulset = import "resources/statefulset.libsonnet";
local db_service = import "resources/service.libsonnet";

{
  // Root component entrypoint: directly mount all database-owned resources.
  manifest(config, _cluster_psm=null): {
    pvc: db_pvc.new(config),
    statefulset: db_statefulset.new(config),
    service: db_service.new(config),
  },
}
