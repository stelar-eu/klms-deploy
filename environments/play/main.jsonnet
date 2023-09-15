local tk_env = import "spec.json";

local declared_items_from_spec = {
    _tk_env:: tk_env.spec,

    _config+:: {
        namespace: tk_env.spec.namespace
    },    

};

local main = (import "play.libsonnet");

main+declared_items_from_spec

