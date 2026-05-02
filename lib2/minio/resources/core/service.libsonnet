local statefulset = import "statefulset.libsonnet";
local svcs = import "../../../util/services.libsonnet";

{
  new(config):
    svcs.serviceFor(statefulset.new(config)),
}
