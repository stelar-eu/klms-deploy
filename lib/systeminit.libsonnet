local kcinit = import "init/kcinit_with_registry.libsonnet";
local apiinit = import "init/apiinit.libsonnet";
local ckaninit = import "init/ckaninit.libsonnet";
local ontopinit = import "init/ontopinit.libsonnet";
local quayinit = import "init/quayinit.libsonnet";
local initrbac = import "init/initrbac.libsonnet";

{
    manifest(pim, config):
        kcinit.manifest(pim, config)
        + apiinit.manifest(pim, config)
        + ckaninit.manifest(pim, config)
        + ontopinit.manifest(pim, config)
        + quayinit.manifest(pim, config)
        + initrbac.manifest(pim, config),
}
