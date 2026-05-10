// Shared manifest transform helpers for lib2 composition.
{
    transform(cluster_psm, component_psms, components): [
        component.entrypoint.manifest(cluster_psm + component_psms[component.name]),
        for component in components
    ],

    transform_pim(_pim, cluster_psm, component_psms, components):
        self.transform(cluster_psm, component_psms, components),
}
