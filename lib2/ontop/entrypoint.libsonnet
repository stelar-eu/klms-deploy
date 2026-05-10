// Stable root entrypoint for the ontop component.
local ontop_deployment = import "resources/deployment.libsonnet";
local ontop_service = import "resources/service.libsonnet";
local ontop_initjob = import "resources/initjob.libsonnet";

{
  // Root component entrypoint: directly mount all Ontop-owned resources.
  manifest(config, _cluster_psm=null): {
    deployment: ontop_deployment.new(config),
    service: ontop_service.new(config),
    initjob: ontop_initjob.new(config),
  },
}
