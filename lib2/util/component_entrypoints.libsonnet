// Static lookup for lib2 component entrypoints.
{
  local registry = {
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
    if std.objectHas(registry, component_name) then
      registry[component_name]
    else
      error "Unknown lib2 component: " + component_name,


}
