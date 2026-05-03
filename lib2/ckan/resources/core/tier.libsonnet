local ckan_deployment = import "deployment.libsonnet";
local ckan_service = import "service.libsonnet";
local ckan_ingress = import "ingress.libsonnet";
local ckan_initjob = import "initjob.libsonnet";

{
  new(config): {
    deployment: ckan_deployment.new(config),
    service: ckan_service.new(),
    ingress: ckan_ingress.new(config),
    initjob: ckan_initjob.new(config),
  },
}
