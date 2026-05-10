// Stable root entrypoint for the ckan component.
local ckan_deployment = import "resources/deployment.libsonnet";
local ckan_service = import "resources/service.libsonnet";
local ckan_ingress = import "resources/ingress.libsonnet";
local ckan_initjob = import "resources/initjob.libsonnet";

{
  // Root component entrypoint: directly mount all CKAN-owned resources.
  manifest(psm): {
    deployment: ckan_deployment.new(psm),
    service: ckan_service.new(psm),
    ingress: ckan_ingress.new(psm),
    initjob: ckan_initjob.new(psm),
  },
}
