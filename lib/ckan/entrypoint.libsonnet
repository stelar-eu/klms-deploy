// Stable root entrypoint for the ckan component.
local ckan_deployment = import "resources/deployment.libsonnet";
local ckan_service = import "resources/service.libsonnet";
local ckan_ingress = import "resources/ingress.libsonnet";
local ckan_initjob = import "resources/initjob.libsonnet";

{
  // Root component entrypoint: directly mount all CKAN-owned resources.
  manifest(config): {
    deployment: ckan_deployment.new(config),
    service: ckan_service.new(config),
    ingress: ckan_ingress.new(config),
    initjob: ckan_initjob.new(config),
  },
}
