// Static registry for lib2 components and their entrypoints.
{
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
  ],

  local entrypoints = {
    system: import "../system/entrypoint.libsonnet",
    db: import "../db/entrypoint.libsonnet",
    redis: import "../redis/entrypoint.libsonnet",
    solr: import "../solr/entrypoint.libsonnet",
    datapusher: import "../datapusher/entrypoint.libsonnet",
    ontop: import "../ontop/entrypoint.libsonnet",
    minio: import "../minio/entrypoint.libsonnet",
    keycloak: import "../keycloak/entrypoint.libsonnet",
    stelarapi: import "../stelarapi/entrypoint.libsonnet",
    ckan: import "../ckan/entrypoint.libsonnet",
    registry: import "../registry/entrypoint.libsonnet",
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
