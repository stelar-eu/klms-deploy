// Stable root entrypoint for the redis component.
local redis_deployment = import "resources/deployment.libsonnet";
local redis_service = import "resources/service.libsonnet";

{
  // Root component entrypoint: directly mount all Redis-owned resources.
  manifest(config, _cluster_psm=null): {
    deployment: redis_deployment.new(config),
    service: redis_service.new(config),
  },
}
