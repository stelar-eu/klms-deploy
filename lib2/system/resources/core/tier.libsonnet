local network_policy = import "network_policy.libsonnet";
local certificates = import "certificates.libsonnet";
local initrbac = import "initrbac.libsonnet";

{
  new(config): {
    networkpolicy: network_policy.new(),
    certificates: certificates.new(config),
    initrbac: initrbac.new(),
  },
}
