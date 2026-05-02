local keycloak_configmap = import "resources/core/configmap.libsonnet";
local keycloak_deployment = import "resources/core/deployment.libsonnet";
local keycloak_service = import "resources/core/service.libsonnet";
local keycloak_initjob = import "resources/core/initjob.libsonnet";

{
  manifest(config): {
    configmap: keycloak_configmap.new(config),
    deployment: keycloak_deployment.new(config),
    service: keycloak_service.new(config),
    initjob: keycloak_initjob.new(config),
  },
}
