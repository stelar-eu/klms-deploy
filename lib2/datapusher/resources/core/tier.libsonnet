// Core tier composition for the datapusher component.
local datapusher_deployment = import "deployment.libsonnet";
local datapusher_service = import "service.libsonnet";

{
  // Core tier composition for Datapusher.
  new(_config): {
    deployment: datapusher_deployment.new(),
    service: datapusher_service.new(),
  },
}
