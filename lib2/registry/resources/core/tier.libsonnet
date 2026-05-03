local registry_deployment = import "deployment.libsonnet";
local registry_service = import "service.libsonnet";
local registry_ingress = import "ingress.libsonnet";
local registry_initjob = import "initjob.libsonnet";

{
  new(config): {
    deployment: registry_deployment.new(config),
    service: registry_service.new(config),
    ingress: registry_ingress.new(config),
    initjob: registry_initjob.new(config),
  },
}
