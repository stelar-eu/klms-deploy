// Core Service constructor for the solr component.
local svcs = import "../../util/services.libsonnet";

{
  new(config):
    svcs.headlessService.new(
      "solr",
      "solr",
      config.solr.PORT,
      "solr"
    )
}
