// Static environment template. The copied environment file is expected to
// provide one cluster PSM plus per-component PSM data under psm/.
local tier_components = import "../util/tier_components.libsonnet";

local cluster_psm = import "psm/cluster.json";
local component_psms = import "psm/components/index.json";
local active_tier = cluster_psm.tier;
local components = tier_components.get(active_tier);

{
  manifests: [
    // Tier membership stays in static Jsonnet; only the selected component PSM
    // and the shared cluster PSM change between environments.
    component.entrypoint.manifest(component_psms[component.name], cluster_psm)
    for component in components
  ],
}
