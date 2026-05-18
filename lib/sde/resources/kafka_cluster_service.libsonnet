// Core Service constructor for the Kafka/Zookeeper cluster inside the sde component.
local deployment = import "kafka_cluster_deployment.libsonnet";
local svcs = import "../../util/services.libsonnet";

{
  new(config):
    svcs.serviceFor(deployment.new(config))
}
