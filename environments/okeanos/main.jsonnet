/************
    This environment contains configuration resources for the 
    okeanos cluster. However, the code here may be useful to other clusters.


 */

local tk_env = import "spec.json";
local cert = import "certificate.libsonnet";

{
    _tk_env:: tk_env.spec,

    _config+:: {
        namespace: tk_env.spec.namespace,

        dynamicStorageClass: "longhorn"
    },    


    letsenc: cert.letsencrypt_clusterissuers("vsamoladas@tuc.gr")
}
