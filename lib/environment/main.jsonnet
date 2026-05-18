// Static environment template. The selected components are rendered from a
// generated product fullspec imported as one shared config object.

local product_transformation = import "../util/product_transformation.libsonnet";
local component_registry = import "../util/components.libsonnet";

local product_fullspec = import "./product_fullspec.json";

local selected_components = std.objectFields(product_transformation.extract_components(product_fullspec));
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
