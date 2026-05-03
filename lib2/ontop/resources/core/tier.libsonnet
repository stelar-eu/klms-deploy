// Core tier composition for the ontop component.
local ontop_deployment = import "deployment.libsonnet";
local ontop_service = import "service.libsonnet";
local ontop_initjob = import "initjob.libsonnet";

{
  // Core tier composition for Ontop and its initialization step.
  new(config): {
    deployment: ontop_deployment.new(config),
    service: ontop_service.new(config),
    initjob: ontop_initjob.new(config),
  },
}
