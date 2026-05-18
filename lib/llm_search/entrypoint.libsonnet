// Stable root entrypoint for the llm_search component.
local llm_search_pvc = import "resources/pvc.libsonnet";
local llm_search_deployment = import "resources/deployment.libsonnet";
local llm_search_service = import "resources/service.libsonnet";

{
  manifest(config): {
    pvc: llm_search_pvc.new(config),
    deployment: llm_search_deployment.new(config),
    service: llm_search_service.new(config),
  },
}
