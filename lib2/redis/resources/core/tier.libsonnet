// Core tier composition for the redis component.
local redis_deployment = import "deployment.libsonnet";
local redis_service = import "service.libsonnet";

{
  // Core tier composition for Redis.
  new(_config): {
    deployment: redis_deployment.new(),
    service: redis_service.new(),
  },
}
