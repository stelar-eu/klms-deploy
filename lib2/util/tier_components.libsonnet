local tiers = {
  core: import "../tiers/core/component_names.libsonnet",
  full: import "../tiers/full/component_names.libsonnet",
};

{
  get(tier_name):
    if std.objectHas(tiers, tier_name) then tiers[tier_name] else tiers.core,
}
