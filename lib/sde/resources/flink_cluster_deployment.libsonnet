// Core Deployment constructor for the Flink cluster inside the sde component.
local k = import "../../util/k.libsonnet";

local deploy = k.apps.v1.deployment;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;

{
  new(config):
    deploy.new(
      name = config.flink.deployment_name,
      containers = [
        container.new(config.flink.jobmanager_container_name, config.images.FLINK_IMAGE)
        + container.withImagePullPolicy(config.flink.image_pull_policy)
        + container.withEnvMap({
          JOB_MANAGER_RPC_ADDRESS: config.flink.jobmanager_rpc_address,
          JOB_MANAGER_REST_PORT: config.flink.jobmanager_rest_port,
        })
        + container.withPorts([
          containerPort.newNamed(config.flink.jobmanager_rpc_port, config.flink.jobmanager_rpc_port_name),
          containerPort.newNamed(config.flink.jobmanager_rest_port_number, config.flink.jobmanager_rest_port_name),
        ])
        + container.withArgs([config.flink.jobmanager_arg]),

        container.new(config.flink.taskmanager_1_container_name, config.images.FLINK_IMAGE)
        + container.withImagePullPolicy(config.flink.image_pull_policy)
        + container.withEnvMap({
          JOB_MANAGER_RPC_ADDRESS: config.flink.jobmanager_rpc_address,
        })
        + container.withPorts([
          containerPort.newNamed(config.flink.taskmanager_1_port, config.flink.taskmanager_1_port_name),
        ])
        + container.withArgs([config.flink.taskmanager_arg]),

        container.new(config.flink.taskmanager_2_container_name, config.images.FLINK_IMAGE)
        + container.withImagePullPolicy(config.flink.image_pull_policy)
        + container.withEnvMap({
          JOB_MANAGER_RPC_ADDRESS: config.flink.jobmanager_rpc_address,
        })
        + container.withPorts([
          containerPort.newNamed(config.flink.taskmanager_2_port, config.flink.taskmanager_2_port_name),
        ])
        + container.withArgs([config.flink.taskmanager_arg]),
      ],
      podLabels = config.flink.labels
    ),
}
