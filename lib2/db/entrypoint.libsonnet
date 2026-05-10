// Stable root entrypoint for the db component.
local db_pvc = import "resources/pvc.libsonnet";
local db_statefulset = import "resources/statefulset.libsonnet";
local db_service = import "resources/service.libsonnet";

{
  // Root component entrypoint: directly mount all database-owned resources.
  manifest(psm): {
    pvc: db_pvc.new(psm),
    statefulset: db_statefulset.new(psm),
    service: db_service.new(psm),
  },
}
