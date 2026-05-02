local k = import "k.libsonnet";

local pvc = k.core.v1.persistentVolumeClaim;


{
/**
    Used to create persistent volume claims
 */
    pvcWithDynamicStorage(name, gibytes, storage_class):
        pvc.new(name)
        + pvc.spec.withStorageClassName(storage_class)
        + pvc.spec.withAccessModes(['ReadWriteOnce'])
        + pvc.spec.withVolumeMode('Filesystem')
        + pvc.spec.resources.withRequests({
            storage: gibytes
        })
}