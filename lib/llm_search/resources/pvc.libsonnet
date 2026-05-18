// Core PersistentVolumeClaim constructor for the llm_search component.
local pvol = import "../../util/pvolumes.libsonnet";

{
  new(config):
    pvol.pvcWithDynamicStorage(
      "chroma-storage",
      "5Gi",
      config.dynamic_volume_storage_class
    )
}
