// Stable root entrypoint for deployment-wide lib2 resources.
local network_policy = import "resources/network_policy.libsonnet";
local certificates = import "resources/certificates.libsonnet";
local initrbac = import "resources/initrbac.libsonnet";

{
  // System composes deployment-wide resources instead of an application
  // workload, but follows the same flat resource pattern as other components.
  manifest(config): {
    networkpolicy: network_policy.new(config),
    certificates: certificates.new(config),
    initrbac: initrbac.new(config),
  },
}
