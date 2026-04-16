local apiinit = import "init/apiinit.libsonnet";
local ckaninit = import "init/ckaninit.libsonnet";
local initrbac = import "init/initrbac.libsonnet";
local kcinit = import "init/kcinit.libsonnet";
local kcinit_with_registry = import "init/kcinit_with_registry.libsonnet";
local ontopinit = import "init/ontopinit.libsonnet";
local quayinit = import "init/quayinit.libsonnet";

local init_jobs_by_tier = {
    core: [
        initrbac,
        kcinit,
        apiinit,
        ckaninit,
    ],
    full: [
        initrbac,
        kcinit_with_registry,
        apiinit,
        ckaninit,
        ontopinit,
        quayinit,
    ],
};

function(tier)
    if !std.objectHas(init_jobs_by_tier, tier) then
        error "Unsupported STELAR tier for system init: " + tier
    else
        {
            manifest(pim, config):
                std.foldl(
                    function(manifest, init_job)
                        manifest + init_job.manifest(pim, config),
                    init_jobs_by_tier[tier],
                    {}
                ),
        }
