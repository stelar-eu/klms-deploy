// Stable root entrypoint for the registry component.
local registry_deployment = import "resources/deployment.libsonnet";
local registry_service = import "resources/service.libsonnet";
local registry_ingress = import "resources/ingress.libsonnet";
local registry_initjob = import "resources/initjob.libsonnet";

{
  // Root component entrypoint: directly mount all registry-owned resources.
  manifest(psm): {
    deployment: registry_deployment.new(psm),
    service: registry_service.new(psm),
    ingress: registry_ingress.new(psm),
    initjob: registry_initjob.new(psm),
  },
}
