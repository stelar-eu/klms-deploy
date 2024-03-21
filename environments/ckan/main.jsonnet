local tk_env = import "spec.json";

/*
local declared_items_from_spec = {
    _tk_env:: tk_env.spec,

    _config+:: {
        namespace: tk_env.spec.namespace,

        dynamicStorageClass: "longhorn"
    },    

};

local main = (import "ckan.libsonnet");

main+declared_items_from_spec
*/

local main = (import "ckan.libsonnet");

main {
    _tk_env:: tk_env.spec,

    _config+:: {
        namespace: tk_env.spec.namespace,

        dynamicStorageClass: "longhorn"
    },    

}
