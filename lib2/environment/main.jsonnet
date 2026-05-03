local tier_components = import "../util/tier_components.libsonnet";

local cluster_psm = import "psm/cluster.json";
local component_psms = import "psm/components/index.json";
local active_tier = cluster_psm.tier;
local components = tier_components.get(active_tier);

{
  manifests: [
    component.entrypoint.manifest(component_psms[active_tier][component.name], cluster_psm)
    for component in components
  ],
}
