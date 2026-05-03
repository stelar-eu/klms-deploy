local tier_selector = import "../util/tier_selector.libsonnet";
local core = import "resources/core/tier.libsonnet";
local full = import "resources/full/tier.libsonnet";
local tiers = {
  core: core,
  full: full,
};

{
  manifest(config): tier_selector.render_selected_tier(config, tiers),
}
