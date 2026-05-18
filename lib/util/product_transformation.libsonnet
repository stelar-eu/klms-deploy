
{
    extract_components(product_fullspec)::
        local root =
            if std.objectHas(product_fullspec, "klms") then
                product_fullspec.klms
            else
                product_fullspec;
        local components =
            (if std.objectHas(root, "core_components") then root.core_components else [])
            + (if std.objectHas(root, "optional_components") then root.optional_components else [])
            + (if std.objectHas(root, "cluster") then root.cluster else []);

        {
            [component]: {}
            for component in components
        },

    extract_configuration(product_fullspec)::
        if std.objectHas(product_fullspec, "klms") then
            product_fullspec.klms
        else
            product_fullspec,
}
