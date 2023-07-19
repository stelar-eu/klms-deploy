local _env_spec = import "spec.json";

(import "stelar.libsonnet") +
{
    _env_spec:: _env_spec,

    _config+:: {
        stelar_ns: _env_spec.spec.namespace,
        grafana: {
            port: 3000,
            name: "grafana",
        },

        prometheus: {
            port: 9090,
            name: "prometheus"
        },

        
    },    

}
