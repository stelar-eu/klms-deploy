// Stable root entrypoint for the stelarapi component.
local api_configmap = import "resources/configmap.libsonnet";
local api_deployment = import "resources/deployment.libsonnet";
local api_service = import "resources/service.libsonnet";
local api_rbac = import "resources/rbac.libsonnet";
local api_initjob = import "resources/initjob.libsonnet";

{
  // Root component entrypoint: directly mount all STELAR API resources.
  manifest(psm): {
    configmap: api_configmap.new(psm),
    deployment: api_deployment.new(psm),
    service: api_service.new(psm),
    rbac: api_rbac.new(psm),
    initjob: api_initjob.new(psm),
  },
}
