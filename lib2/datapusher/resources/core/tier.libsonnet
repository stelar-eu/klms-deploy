local datapusher_deployment = import "deployment.libsonnet";
local datapusher_service = import "service.libsonnet";

{
  new(_config): {
    deployment: datapusher_deployment.new(),
    service: datapusher_service.new(),
  },
}
