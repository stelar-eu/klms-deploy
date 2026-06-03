function(product_fullspec)
  local product_transformation = import "github.com/stelar-eu/klms-deploy/lib/util/product_transformation.libsonnet";
  local component_registry = import "github.com/stelar-eu/klms-deploy/lib/util/components.libsonnet";

  local selected_components = std.objectFields(
    product_transformation.extract_components(product_fullspec)
  );
  local global_config = product_transformation.extract_configuration(product_fullspec);

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
