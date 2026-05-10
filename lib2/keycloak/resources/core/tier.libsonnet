// Core tier composition for the keycloak component.
local keycloak_configmap = import "configmap.libsonnet";
local keycloak_deployment = import "deployment.libsonnet";
local keycloak_service = import "service.libsonnet";
local keycloak_initjob = import "initjob.libsonnet";

{
  // Core tier composition for Keycloak and its bootstrap job.
  new(config): {
    configmap: keycloak_configmap.new(config),
    deployment: keycloak_deployment.new(config),
    service: keycloak_service.new(config),
    initjob: keycloak_initjob.new(config),
  },
}
