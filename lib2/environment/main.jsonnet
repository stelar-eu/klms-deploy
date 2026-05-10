// Static environment template. The copied environment file is expected to
// provide one cluster PSM plus per-component PSM data under psm/.
local component_entrypoints = import "../util/component_entrypoints.libsonnet";
local component_names = [
  "system",
  "db",
  "redis",
  "solr",
  "datapusher",
  "ontop",
  "minio",
  "keycloak",
  "stelarapi",
  "ckan",
  "registry",
];
local components = component_entrypoints.get_many(component_names);

local cluster_psm = import "psm/cluster.json";
local component_psms = import "psm/components/index.json";

{
  manifests: [
    // Component membership is static in this template; only the selected PSM
    // data changes between environments.
    component.entrypoint.manifest(component_psms[component.name], cluster_psm)
    for component in components
  ],
}
