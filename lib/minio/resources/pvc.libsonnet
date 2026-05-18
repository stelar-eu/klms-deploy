// Core PersistentVolumeClaim constructor for the minio component.
local pvol = import "../../util/pvolumes.libsonnet";

{
  new(config):
    pvol.pvcWithDynamicStorage(
      "minio-storage",
      "2Gi",
      config.dynamic_volume_storage_class
    )
}
