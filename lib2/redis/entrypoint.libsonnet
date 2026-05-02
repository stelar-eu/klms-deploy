local redis_deployment = import "resources/core/deployment.libsonnet";
local redis_service = import "resources/core/service.libsonnet";

{
  manifest(_config): {
    deployment: redis_deployment.new(),
    service: redis_service.new(),
  },
}
