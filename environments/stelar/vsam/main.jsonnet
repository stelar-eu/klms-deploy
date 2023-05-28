// local k = import "github.com/grafana/jsonnet-libs/ksonnet-util/kausal.libsonnet";
local _env_spec = import "spec.json";
(import "stelar.libsonnet") +
{
    _env_spec:: _env_spec,

    _config:: {
        stelar_ns: _env_spec.spec.namespace,
        grafana: {
            port: 3000,
            name: "grafana",
        },
        prometheus: {
            port: 9090,
            name: "prometheus"
        }
    },    

/*
    local namespace = k.core.v1.namespace,
    local deployment = k.apps.v1.deployment,
    local container = k.core.v1.container,
    local port = k.core.v1.containerPort,
    local service = k.core.v1.service,

    stelar_namespace: namespace.new($._config.stelar_ns),
    //stelar_namespace: namespace.new($._env_spec.spec.namespace),
*/
}
