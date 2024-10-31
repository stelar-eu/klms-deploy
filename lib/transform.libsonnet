/*
    Transformation routines

 */

{
    transform_pim(pim, config, components): [
        component.manifest(pim, config),
        for component in components
    ],
}