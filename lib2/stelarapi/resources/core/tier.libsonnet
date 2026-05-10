// Core tier composition for the stelarapi component.
local api_configmap = import "configmap.libsonnet";
local api_deployment = import "deployment.libsonnet";
local api_service = import "service.libsonnet";
local api_rbac = import "rbac.libsonnet";
local api_initjob = import "initjob.libsonnet";

{
  // Core tier composition for the STELAR API and its support resources.
  new(config): {
    configmap: api_configmap.new(config),
    deployment: api_deployment.new(config),
    service: api_service.new(config),
    rbac: api_rbac.new(),
    initjob: api_initjob.new(config),
  },
}
