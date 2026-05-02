local ckan_deployment = import "resources/core/deployment.libsonnet";
local ckan_service = import "resources/core/service.libsonnet";
local ckan_ingress = import "resources/core/ingress.libsonnet";
local ckan_initjob = import "resources/core/initjob.libsonnet";

{
  manifest(config): {
    deployment: ckan_deployment.new(config),
    service: ckan_service.new(),
    ingress: ckan_ingress.new(config),
    initjob: ckan_initjob.new(config),
  },
}
