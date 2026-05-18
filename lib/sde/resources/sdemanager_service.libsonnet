// Core Service constructor for the SDE Manager UI inside the sde component.
local deployment = import "sdemanager_deployment.libsonnet";
local svcs = import "../../util/services.libsonnet";

{
  new(config):
    svcs.serviceFor(deployment.new(config))
}
