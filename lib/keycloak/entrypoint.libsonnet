// Stable root entrypoint for the keycloak component.
local keycloak_configmap = import "resources/configmap.libsonnet";
local keycloak_deployment = import "resources/deployment.libsonnet";
local keycloak_service = import "resources/service.libsonnet";
local keycloak_initjob = import "resources/initjob.libsonnet";

{
  // Root component entrypoint: directly mount all Keycloak-owned resources.
  manifest(config): {
    configmap: keycloak_configmap.new(config),
    deployment: keycloak_deployment.new(config),
    service: keycloak_service.new(config),
    initjob: keycloak_initjob.new(config),
  },
}
