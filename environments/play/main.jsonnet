local tk_env = import "spec.json";

(import "play.libsonnet") +
{
    _tk_env:: tk_env.spec,

    _config+:: {
        namespace: tk_env.spec.namespace
    },    

}
