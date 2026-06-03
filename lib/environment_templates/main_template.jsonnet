local build_lake = import "github.com/stelar-eu/klms-deploy/lib/util/build_lake.libsonnet";
local product_fullspec = import "./product_fullspec.json";

build_lake(product_fullspec)
