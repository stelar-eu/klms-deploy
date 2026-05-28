// Core Service constructor for the Kafbat UI inside the sde component.
local deployment = import "kafbat_deployment.libsonnet";
local svcs = import "../../util/services.libsonnet";

{
  new(config):
    svcs.serviceFor(deployment.new(config))
}
