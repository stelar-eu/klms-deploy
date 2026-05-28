// Core Deployment constructor for the Kafka/Zookeeper cluster inside the sde component.
local k = import "../../util/k.libsonnet";

local deploy = k.apps.v1.deployment;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;

local kafka_env(config, broker_order) = {
  KAFKA_ZOOKEEPER_CONNECT: "localhost:" + std.toString(config.zookeeper.port),
  KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: config.kafka.listener_security_protocol_map,
  KAFKA_INTER_BROKER_LISTENER_NAME: config.kafka.inter_broker_listener_name,
  KAFKA_LISTENERS: "INTERNAL://0.0.0.0:" + std.toString(config.kafka.internal_port + broker_order - 1) + ",EXTERNAL://0.0.0.0:" + std.toString(broker_order) + std.toString(config.kafka.internal_port),
  KAFKA_ADVERTISED_LISTENERS: "INTERNAL://localhost:" + std.toString(config.kafka.internal_port + broker_order - 1) + ",EXTERNAL://kafka-cluster:" + std.toString(broker_order) + std.toString(config.kafka.internal_port),
  KAFKA_BROKER_ID: std.toString(broker_order),
  KAFKA_MIN_INSYNC_REPLICAS: config.kafka.min_insync_replicas,
  KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: config.kafka.offsets_topic_replication_factor,
};

{
  new(config):
    deploy.new(
      name = config.kafka.deployment_name,
      containers = [
        container.new(config.kafka.broker_1_container_name, config.images.KAFKA_IMAGE)
        + container.withImagePullPolicy(config.kafka.image_pull_policy)
        + container.withEnvMap(kafka_env(config, 1))
        + container.withPorts([
          containerPort.newNamed(config.kafka.broker_1_external_port, config.kafka.broker_1_port_name),
        ]),

        container.new(config.kafka.broker_2_container_name, config.images.KAFKA_IMAGE)
        + container.withImagePullPolicy(config.kafka.image_pull_policy)
        + container.withEnvMap(kafka_env(config, 2))
        + container.withPorts([
          containerPort.newNamed(config.kafka.broker_2_external_port, config.kafka.broker_2_port_name),
        ]),

        container.new(config.zookeeper.container_name, config.images.ZOOKEEPER_IMAGE)
        + container.withImagePullPolicy(config.zookeeper.image_pull_policy)
        + container.withEnvMap({
          ZOOKEEPER_CLIENT_PORT: std.toString(config.zookeeper.port),
          ZOOKEEPER_TICK_TIME: config.zookeeper.tick_time,
        })
        + container.withPorts([
          containerPort.newNamed(config.zookeeper.port, config.zookeeper.port_name),
        ]),
      ],
      podLabels = config.kafka.labels
    ),
}
