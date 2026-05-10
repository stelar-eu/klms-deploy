// Stable root entrypoint for the datapusher component.
local datapusher_deployment = import "resources/deployment.libsonnet";
local datapusher_service = import "resources/service.libsonnet";

{
  // Root component entrypoint: directly mount all Datapusher-owned resources.
  manifest(psm): {
    deployment: datapusher_deployment.new(psm),
    service: datapusher_service.new(psm),
  },
}
