// Core tier composition for deployment-wide lib2 resources.
local network_policy = import "network_policy.libsonnet";
local certificates = import "certificates.libsonnet";
local initrbac = import "initrbac.libsonnet";

{
  // Core tier composition for deployment-wide resources.
  new(config): {
    networkpolicy: network_policy.new(),
    certificates: certificates.new(config),
    initrbac: initrbac.new(),
  },
}
