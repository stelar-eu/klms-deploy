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

    default_params: {

    },

    new(params): 
        local all_params = self.default_params + params;
        helm.template("postgres", "../charts/postgresql", all_params) + {

        /*
            Set the size of the persistent volume claim of volume 'data' to
            the argument, which must be suitable for a storage, e.g.  '2Gi'
         */
        setDataStorageSize(storage):: self {
            /*
                Get the stateful set from within.
            */   
            local sset = super.stateful_set_postgres_postgresql,
            local old_pvct = sset.spec.volumeClaimTemplates[0],
            local rest_pvcts = sset.spec.volumeClaimTemplates[1:],
            local new_pvct = old_pvct + pvctmpl.spec.resources.withRequestsMixin({storage: storage}),

            /* 
                Pack the updated stateful set into the chart
            */
            local new_pvcts = [new_pvct],
            assert std.length(rest_pvcts)==0 : "SEMANTIC: there are multiple volumeClaimTemplate entities",
            assert new_pvct.metadata.name == 'datum' : "SEMANTIC: The data volume claim is not foon",


            stateful_set_postgres_postgresql+: stateful.spec.withVolumeClaimTemplates(new_pvcts)
        }
    },

}