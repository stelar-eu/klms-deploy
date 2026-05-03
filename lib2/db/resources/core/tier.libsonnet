// Core tier composition for the db component.
local db_pvc = import "pvc.libsonnet";
local db_statefulset = import "statefulset.libsonnet";
local db_service = import "service.libsonnet";

{
  // Core tier composition for the shared Postgres database.
  new(config): {
    pvc: db_pvc.new(),
    statefulset: db_statefulset.new(config),
    service: db_service.new(),
  },
}
