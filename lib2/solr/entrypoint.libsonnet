local solr_pvc = import "resources/core/pvc.libsonnet";
local solr_statefulset = import "resources/core/statefulset.libsonnet";
local solr_service = import "resources/core/service.libsonnet";

{
  manifest(_config): {
    pvc: solr_pvc.new(),
    statefulset: solr_statefulset.new(),
    service: solr_service.new(),
  },
}
