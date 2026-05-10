// Stable root entrypoint for the ontop component.
local ontop_deployment = import "resources/deployment.libsonnet";
local ontop_service = import "resources/service.libsonnet";
local ontop_initjob = import "resources/initjob.libsonnet";

{
  // Root component entrypoint: directly mount all Ontop-owned resources.
  manifest(psm): {
    deployment: ontop_deployment.new(psm),
    service: ontop_service.new(psm),
    initjob: ontop_initjob.new(psm),
  },
}
