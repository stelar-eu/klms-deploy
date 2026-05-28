// Stable root entrypoint for the visualizer component.
local visualizer_deployment = import "resources/deployment.libsonnet";
local visualizer_service = import "resources/service.libsonnet";

{
  manifest(config): {
    deployment: visualizer_deployment.new(config),
    service: visualizer_service.new(config),
  },
}
