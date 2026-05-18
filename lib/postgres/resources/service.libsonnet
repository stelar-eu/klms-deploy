// Core Service constructor for the db component.
local svcs = import "../../util/services.libsonnet";

{
  new(config):
    svcs.headlessService.new(
      "db",
      "postgis",
      config.postgres.PORT
    )
}
