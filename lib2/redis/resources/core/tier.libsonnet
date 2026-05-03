local redis_deployment = import "deployment.libsonnet";
local redis_service = import "service.libsonnet";

{
  new(_config): {
    deployment: redis_deployment.new(),
    service: redis_service.new(),
  },
}
