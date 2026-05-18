// Stable root entrypoint for the stelarapi component.
local api_configmap = import "resources/configmap.libsonnet";
local api_deployment = import "resources/deployment.libsonnet";
local api_service = import "resources/service.libsonnet";
local api_rbac = import "resources/rbac.libsonnet";
local api_initjob = import "resources/initjob.libsonnet";

{
  // Root component entrypoint: directly mount all STELAR API resources.
  manifest(config): {
    configmap: api_configmap.new(config),
    deployment: api_deployment.new(config),
    service: api_service.new(config),
    rbac: api_rbac.new(config),
    initjob: api_initjob.new(config),
  },
}
