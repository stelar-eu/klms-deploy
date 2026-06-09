local build_lake = import "github.com/stelar-eu/klms-deploy/lib/util/build_lake.libsonnet";
local environment_spec = import "./spec.json";

build_lake(environment_spec)
