// Core PersistentVolumeClaim constructor for the solr component.
local pvol = import "../../util/pvolumes.libsonnet";

{
  new(config):
    pvol.pvcWithDynamicStorage(
      "solr-data",
      "5Gi",
      config.dynamic_volume_storage_class
    )
}
