/*
    Transformation routines

 */


{
    transform_psm(psm, components): [
        component.manifest(psm),
        for component in components
    ],
}