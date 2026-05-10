// Static environment template. The copied environment file is expected to
// provide one cluster PSM plus per-component PSM data under psm/.
local components = import "../util/components.libsonnet";

local cluster_psm = import "psm/cluster.json";
local component_psms = import "psm/components/index.json";

{
  manifests: [
    // Component membership is static in this template; only the selected PSM
    // data changes between environments. Shared cluster data is merged into
    // the component PSM before rendering.
    components.get(component).manifest(cluster_psm + component_psms[component])


    // .get_names() now lists all components, 
    //but according to the product selected from the user, 
    //the method should change to return only the components that are relevant for that product. 
    //For now, we keep it static and return all components, but in the future, we can implement a filter based on the selected product.
    for component in components.get_names()
  ],
}
