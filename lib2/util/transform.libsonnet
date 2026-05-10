// Shared manifest transform helpers for lib2 composition.
{
    transform(config, components): [
        component.manifest(config),
        for component in components
    ],

    transform_pim(_pim, config, components): self.transform(config, components),
}
