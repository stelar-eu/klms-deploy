// Core Service constructor for the ckan component.
local pim = import "../../pim.libsonnet";
local system_pim = import "../../../system/pim.libsonnet";
local svcs = import "../../../util/services.libsonnet";

{
  new():
    svcs.headlessService.new(
      pim.service.name,
      pim.service.component,
      system_pim.ports.CKAN,
      pim.service.port_name
    ),
}
