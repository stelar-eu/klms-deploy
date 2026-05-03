// Core Service constructor for the redis component.
local deployment = import "deployment.libsonnet";
local svcs = import "../../../util/services.libsonnet";

{
  new():
    svcs.serviceFor(deployment.new()),
}
