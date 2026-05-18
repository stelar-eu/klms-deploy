// Core Service constructor for the Flink cluster inside the sde component.
local deployment = import "flink_cluster_deployment.libsonnet";
local svcs = import "../../util/services.libsonnet";

{
  new(config):
    svcs.serviceFor(deployment.new(config))
}
