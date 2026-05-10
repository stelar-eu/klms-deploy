// Static tier-to-component-list lookup used by environment composition.
local tiers = {
  core: import "../tiers/core/component_names.libsonnet",
  full: import "../tiers/full/component_names.libsonnet",
};

{
  // Environment composition selects a static tier list and then loops over the
  // declared component metadata for that tier.
  get(tier_name):
    if std.objectHas(tiers, tier_name) then tiers[tier_name] else tiers.core,
}
