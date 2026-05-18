// Stable root entrypoint for the sde component.
local kafbat_deployment = import "resources/kafbat_deployment.libsonnet";
local kafbat_service = import "resources/kafbat_service.libsonnet";
local kafka_cluster_deployment = import "resources/kafka_cluster_deployment.libsonnet";
local kafka_cluster_service = import "resources/kafka_cluster_service.libsonnet";
local flink_cluster_deployment = import "resources/flink_cluster_deployment.libsonnet";
local flink_cluster_service = import "resources/flink_cluster_service.libsonnet";
local sdemanager_deployment = import "resources/sdemanager_deployment.libsonnet";
local sdemanager_service = import "resources/sdemanager_service.libsonnet";

{
  manifest(config): {
    kafbat_deployment: kafbat_deployment.new(config),
    kafbat_service: kafbat_service.new(config),
    kafka_cluster_deployment: kafka_cluster_deployment.new(config),
    kafka_cluster_service: kafka_cluster_service.new(config),
    flink_cluster_deployment: flink_cluster_deployment.new(config),
    flink_cluster_service: flink_cluster_service.new(config),
    sdemanager_deployment: sdemanager_deployment.new(config),
    sdemanager_service: sdemanager_service.new(config),
  },
}
