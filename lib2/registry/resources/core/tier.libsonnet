// Core tier composition for the registry component.
local registry_deployment = import "deployment.libsonnet";
local registry_service = import "service.libsonnet";
local registry_ingress = import "ingress.libsonnet";
local registry_initjob = import "initjob.libsonnet";

{
  // Core tier composition for the Quay registry and its bootstrap job.
  new(config): {
    deployment: registry_deployment.new(config),
    service: registry_service.new(config),
    ingress: registry_ingress.new(config),
    initjob: registry_initjob.new(config),
  },
}
