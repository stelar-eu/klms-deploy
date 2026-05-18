// Stable root entrypoint for the previewer component.
local previewer_deployment = import "resources/deployment.libsonnet";
local previewer_service = import "resources/service.libsonnet";

{
  manifest(config): {
    deployment: previewer_deployment.new(config),
    service: previewer_service.new(config),
  },
}
