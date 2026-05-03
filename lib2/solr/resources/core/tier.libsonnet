local solr_pvc = import "pvc.libsonnet";
local solr_statefulset = import "statefulset.libsonnet";
local solr_service = import "service.libsonnet";

{
  new(_config): {
    pvc: solr_pvc.new(),
    statefulset: solr_statefulset.new(),
    service: solr_service.new(),
  },
}
