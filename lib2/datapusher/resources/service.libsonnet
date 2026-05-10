// Core Service constructor for the datapusher component.
local deployment = import "deployment.libsonnet";
local svcs = import "../../util/services.libsonnet";

{
  new(_config):
    svcs.serviceFor(deployment.new())
}
