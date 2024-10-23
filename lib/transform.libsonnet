/*
    Transformation routines

 */

{
    transform_pim_psm(pim, psm, components): [
        component.manifest(pim, psm),
        for component in components
    ],
}