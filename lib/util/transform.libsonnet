// Shared manifest transform helpers for lib2 composition.
{
    transform(configs, components): [
        component.entrypoint.manifest(configs[component.name]),
        for component in components
    ],

    transform_pim(configs, components):
        self.transform(configs, components),
}
