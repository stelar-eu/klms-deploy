// Static environment template. The copied environment file is expected to
// provide one cluster PSM plus per-component PSM data under psm/.
local component_entrypoints = import "../util/component_entrypoints.libsonnet";
local components = [
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

local cluster_psm = import "psm/cluster.json";
local component_psms = import "psm/components/index.json";

{
  manifests: [
    // Component membership is static in this template; only the selected PSM
    // data changes between environments. Shared cluster data is merged into
    // the component PSM before rendering.
    component_entrypoints.get(component).manifest(cluster_psm + component_psms[component])
    for component in components
  ],
}
