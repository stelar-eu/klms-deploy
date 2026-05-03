local keycloak_configmap = import "configmap.libsonnet";
local keycloak_deployment = import "deployment.libsonnet";
local keycloak_service = import "service.libsonnet";
local keycloak_initjob = import "initjob.libsonnet";

{
  new(config): {
    configmap: keycloak_configmap.new(config),
    deployment: keycloak_deployment.new(config),
    service: keycloak_service.new(config),
    initjob: keycloak_initjob.new(config),
  },
}
