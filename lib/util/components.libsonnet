// Static registry for lib2 components and their entrypoints.
{
  local component_names = [
    "system",
    "postgres",
    "redis",
    "solr",
    "datapusher",
    "ontop",
    "minio",
    "keycloak",
    "api",
    "ckan",
    "quay",
    "llm_search",
    "prometheus",
    "grafana",
  ],

  local entrypoints = {
    system: import "../system/entrypoint.libsonnet",
    postgres: import "../postgres/entrypoint.libsonnet",
    redis: import "../redis/entrypoint.libsonnet",
    solr: import "../solr/entrypoint.libsonnet",
    datapusher: import "../datapusher/entrypoint.libsonnet",
    ontop: import "../ontop/entrypoint.libsonnet",
    minio: import "../minio/entrypoint.libsonnet",
    keycloak: import "../keycloak/entrypoint.libsonnet",
    api: import "../api/entrypoint.libsonnet",
    ckan: import "../ckan/entrypoint.libsonnet",
    quay: import "../quay/entrypoint.libsonnet",
    llm_search: import "../llm_search/entrypoint.libsonnet",
    prometheus: import "../prometheus/entrypoint.libsonnet",
    grafana: import "../grafana/entrypoint.libsonnet",
  },

  // Fetch one component entrypoint by component name.
  get(component_name):
    if std.objectHas(entrypoints, component_name) then
      entrypoints[component_name]
    else
      error "Unknown lib2 component: " + component_name,

  // Return the static ordered component-name list.
  get_names(): component_names,
}
