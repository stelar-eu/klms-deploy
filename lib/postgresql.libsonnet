/* 
    A model for creating postgresql database services

    {
        name: service name
        image: image name 

    }
*/

local k = import "k.libsonnet";
local tanka = import 'github.com/grafana/jsonnet-libs/tanka-util/main.libsonnet';
local helm = tanka.helm.new(std.thisFile);

local pvctmpl = k.core.v1.persistentVolumeClaimTemplate;
local stateful = k.apps.v1.statefulSet;
{

    /*
        Intstantiate the helm chart from bitnami, configure the namespace.

        It contains:
        1) a secret with the password of user 'postgres'
        2) two services (N.B. why 2?)
        3) the stateful set with a single replica.

    */
    new(namespace): helm.template("postgres", "../charts/postgresql", {
        namespace: namespace,
    }), 


    setStorageRequest(chart, storage): {
        /*
            Get the stateful set from within.
            Change the volumeClaimTemplate storage request to 2 GiB (it was 8GiB by default)
        */   
        local sset = chart.stateful_set_postgres_postgresql,
        local old_pvct = sset.spec.volumeClaimTemplates[0],
        local new_pvct = old_pvct + pvctmpl.spec.resources.withRequestsMixin({storage: storage}),

        /* 
            Pack the updated stateful set into the chart
        */
        local pg2 = chart {
            stateful_set_postgres_postgresql+: sset + stateful.spec.withVolumeClaimTemplates([new_pvct])
        },

        postgres: pg2,
    }.postgres

}