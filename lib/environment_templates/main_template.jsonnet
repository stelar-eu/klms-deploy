local build_lake = import "lib/util/build_lake.libsonnet";
local environment_spec = import "./spec.json";

build_lake(environment_spec)
