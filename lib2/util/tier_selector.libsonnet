// Shared tier selection helpers used by component entrypoints.
{
  // Components own their tier implementations locally, but the default tier
  // fallback is shared so every entrypoint behaves the same way.
  resolve_tier_name(config):
    if std.objectHas(config, "tier") then config.tier else "core",

  render_selected_tier(config, tiers): tiers[self.resolve_tier_name(config)].new(config),
}
