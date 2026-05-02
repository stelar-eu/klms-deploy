local datapusher_deployment = import "resources/core/deployment.libsonnet";
local datapusher_service = import "resources/core/service.libsonnet";

{
  manifest(_config):
    {
      deployment: datapusher_deployment.new(),
      service: datapusher_service.new(),
    },
}
