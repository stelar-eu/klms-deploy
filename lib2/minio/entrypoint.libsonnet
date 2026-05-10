// Stable root entrypoint for the minio component.
local tier_selector = import "../util/tier_selector.libsonnet";
local core = import "resources/core/tier.libsonnet";
local full = import "resources/full/tier.libsonnet";
local tiers = {
  core: core,
  full: full,
};

{
  // Root component entrypoint: select the tier implementation, then let that
  // tier compose the concrete Kubernetes resources for this component.
  manifest(config): tier_selector.render_selected_tier(config, tiers),
}
