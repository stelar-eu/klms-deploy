local registry_deployment = import "resources/core/deployment.libsonnet";
local registry_service = import "resources/core/service.libsonnet";
local registry_ingress = import "resources/core/ingress.libsonnet";
local registry_initjob = import "resources/core/initjob.libsonnet";

{
  manifest(config): {
    deployment: registry_deployment.new(config),
    service: registry_service.new(config),
    ingress: registry_ingress.new(config),
    initjob: registry_initjob.new(config),
  },
}
