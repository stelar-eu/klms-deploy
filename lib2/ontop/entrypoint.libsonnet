local ontop_deployment = import "resources/core/deployment.libsonnet";
local ontop_service = import "resources/core/service.libsonnet";
local ontop_initjob = import "resources/core/initjob.libsonnet";

{
  manifest(config): {
    deployment: ontop_deployment.new(config),
    service: ontop_service.new(config),
    initjob: ontop_initjob.new(config),
  },
}
