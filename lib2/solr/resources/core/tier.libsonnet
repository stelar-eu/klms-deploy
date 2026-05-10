// Core tier composition for the solr component.
local solr_pvc = import "pvc.libsonnet";
local solr_statefulset = import "statefulset.libsonnet";
local solr_service = import "service.libsonnet";

{
  // Core tier composition for Solr.
  new(_config): {
    pvc: solr_pvc.new(),
    statefulset: solr_statefulset.new(),
    service: solr_service.new(),
  },
}
