// Core PersistentVolumeClaim constructor for the db component.
local pvol = import "../../util/pvolumes.libsonnet";

{
  new(config):
    pvol.pvcWithDynamicStorage(
      "postgis-storage",
      "5Gi",
      config.dynamic_volume_storage_class
    )
}
