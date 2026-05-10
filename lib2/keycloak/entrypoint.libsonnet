// Stable root entrypoint for the keycloak component.
local keycloak_configmap = import "resources/configmap.libsonnet";
local keycloak_deployment = import "resources/deployment.libsonnet";
local keycloak_service = import "resources/service.libsonnet";
local keycloak_initjob = import "resources/initjob.libsonnet";

{
  // Root component entrypoint: directly mount all Keycloak-owned resources.
  manifest(psm): {
    configmap: keycloak_configmap.new(psm),
    deployment: keycloak_deployment.new(psm),
    service: keycloak_service.new(psm),
    initjob: keycloak_initjob.new(psm),
  },
}
