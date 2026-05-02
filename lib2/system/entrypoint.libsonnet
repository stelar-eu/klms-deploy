local network_policy = import "resources/core/network_policy.libsonnet";
local certificates = import "resources/core/certificates.libsonnet";
local initrbac = import "resources/core/initrbac.libsonnet";

{
  manifest(config): {
    networkpolicy: network_policy.new(),
    certificates: certificates.new(config),
    initrbac: initrbac.new(),
  },
}
