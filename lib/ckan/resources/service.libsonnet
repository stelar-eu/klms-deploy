// Core Service constructor for the ckan component.
local svcs = import "../../util/services.libsonnet";

{
  new(config):
    svcs.headlessService.new(
      "ckan",
      "ckan",
      config.ckan.PORT,
      "api"
    )
}
