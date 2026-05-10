// Stable root entrypoint for deployment-wide lib2 resources.
local tier_selector = import "../util/tier_selector.libsonnet";
local core = import "resources/core/tier.libsonnet";
local full = import "resources/full/tier.libsonnet";
local tiers = {
  core: core,
  full: full,
};

{
  // System uses the same tier-selection mechanism as product components, but
  // composes deployment-wide resources instead of an application workload.
  manifest(config): tier_selector.render_selected_tier(config, tiers),
}
