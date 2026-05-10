// Core PersistentVolumeClaim constructor for the minio component.
local pim = import "../../pim.libsonnet";
local system_pim = import "../../../system/pim.libsonnet";
local pvol = import "../../../util/pvolumes.libsonnet";

{
  new():
    pvol.pvcWithDynamicStorage(
      pim.pvc.name,
      pim.pvc.size,
      system_pim.dynamic_volume_storage_class
    ),
}
