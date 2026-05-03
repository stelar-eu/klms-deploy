// Static tier metadata for the core deployment. Each item carries the stable
// component name plus the entrypoint that will receive that component's PSM.
[
  {
    name: "system",
    entrypoint: import "../../system/entrypoint.libsonnet",
  },
  {
    name: "db",
    entrypoint: import "../../db/entrypoint.libsonnet",
  },
  {
    name: "redis",
    entrypoint: import "../../redis/entrypoint.libsonnet",
  },
  {
    name: "solr",
    entrypoint: import "../../solr/entrypoint.libsonnet",
  },
  {
    name: "datapusher",
    entrypoint: import "../../datapusher/entrypoint.libsonnet",
  },
  {
    name: "ontop",
    entrypoint: import "../../ontop/entrypoint.libsonnet",
  },
  {
    name: "minio",
    entrypoint: import "../../minio/entrypoint.libsonnet",
  },
  {
    name: "keycloak",
    entrypoint: import "../../keycloak/entrypoint.libsonnet",
  },
  {
    name: "stelarapi",
    entrypoint: import "../../stelarapi/entrypoint.libsonnet",
  },
  {
    name: "ckan",
    entrypoint: import "../../ckan/entrypoint.libsonnet",
  },
  {
    name: "registry",
    entrypoint: import "../../registry/entrypoint.libsonnet",
  },
]
