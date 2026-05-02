local api_configmap = import "resources/core/configmap.libsonnet";
local api_deployment = import "resources/core/deployment.libsonnet";
local api_service = import "resources/core/service.libsonnet";
local api_rbac = import "resources/core/rbac.libsonnet";
local api_initjob = import "resources/core/initjob.libsonnet";

{
  manifest(config): {
    configmap: api_configmap.new(config),
    deployment: api_deployment.new(config),
    service: api_service.new(config),
    rbac: api_rbac.new(),
    initjob: api_initjob.new(config),
  },
}
