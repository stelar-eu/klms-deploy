// Core Service constructor for the registry component.
local deployment = import "deployment.libsonnet";
local svcs = import "../../../util/services.libsonnet";

{
  new(config):
    svcs.serviceFor(deployment.new(config)),
}
