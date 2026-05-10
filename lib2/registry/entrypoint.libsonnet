// Stable root entrypoint for the registry component.
local registry_deployment = import "resources/deployment.libsonnet";
local registry_service = import "resources/service.libsonnet";
local registry_ingress = import "resources/ingress.libsonnet";
local registry_initjob = import "resources/initjob.libsonnet";

{
  // Root component entrypoint: directly mount all registry-owned resources.
  manifest(config, _cluster_psm=null): {
    deployment: registry_deployment.new(config),
    service: registry_service.new(config),
    ingress: registry_ingress.new(config),
    initjob: registry_initjob.new(config),
  },
}
