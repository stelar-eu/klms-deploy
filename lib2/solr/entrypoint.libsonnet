// Stable root entrypoint for the solr component.
local solr_pvc = import "resources/pvc.libsonnet";
local solr_statefulset = import "resources/statefulset.libsonnet";
local solr_service = import "resources/service.libsonnet";

{
  // Root component entrypoint: directly mount all Solr-owned resources.
  manifest(psm): {
    pvc: solr_pvc.new(psm),
    statefulset: solr_statefulset.new(psm),
    service: solr_service.new(psm),
  },
}
