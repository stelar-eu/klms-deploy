function(environment_spec)
  local product_transformation = import "lib/util/product_transformation.libsonnet";
  local component_registry = import "lib/util/components.libsonnet";

  local tk_spec =
    assert std.objectHas(environment_spec, "spec") : "environment spec must define spec";
    environment_spec.spec;
  local product_fullspec =
    assert std.objectHas(tk_spec, "stelar") : "environment spec must define spec.stelar";
    assert std.objectHas(tk_spec.stelar, "active_product") : "environment spec must define spec.stelar.active_product";
    tk_spec.stelar.active_product;
  local namespace =
    assert std.objectHas(tk_spec, "namespace") : "environment spec must define spec.namespace";
    tk_spec.namespace;
  local selected_components = std.objectFields(
    product_transformation.extract_components(product_fullspec)
  );
  local global_config = product_transformation.extract_configuration(product_fullspec) + {
    environment: {
      namespace: namespace,
      contextName:
        if std.objectHas(tk_spec, "contextNames") && std.length(tk_spec.contextNames) == 1 then
          tk_spec.contextNames[0]
        else
          null,
    },
  };

  local render_order = [
    name
    for name in component_registry.get_names()
    if std.member(selected_components, name)
  ];

  {
    manifests: [
      component_registry.get(name).manifest(global_config)
      for name in render_order
    ],
  }
