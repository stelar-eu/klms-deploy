local tk_env = import "spec.json";


local ckan = import "ckan.libsonnet";
local db = import "db.libsonnet";
local ontop = import "ontop.libsonnet";
local stelarapi = import "stelarapi.libsonnet";

db +
ckan +
ontop + 
stelarapi +
{

    _tk_env:: tk_env.spec,

    _config+:: {
        namespace: tk_env.spec.namespace,

        dynamicStorageClass: "longhorn"
    },    


    /****************************
        Ingress for the data catalog

     */

    local k = import "k.libsonnet",

    local ing = k.networking.v1.ingress,
    local ingrule = k.networking.v1.ingressRule,
    local ingpath = k.networking.v1.httpIngressPath,

    ingress: ing.new("data-catalog")
        + ing.metadata.withAnnotations({
            "cert-manager.io/cluster-issuer": "letsencrypt-production",
            "nginx.ingress.kubernetes.io/proxy-connect-timeout": "60s",
            "nginx.ingress.kubernetes.io/ssl-redirect": "true",
            "nginx.ingress.kubernetes.io/x-forwarded-prefix": "/$1",
            "nginx.ingress.kubernetes.io/rewrite-target": "/$3",
        })
        + ing.spec.withIngressClassName("nginx")
        + ing.spec.withRules([
            ingrule.withHost("stelar.vsamtuc.top")
            + ingrule.http.withPaths([

                /*
                    CKAN

                */
                ingpath.withPath("/(dc)(/|$)(.*)")
                + ingpath.withPathType("Prefix")
                + ingpath.backend.service.withName("ckan")
                + ingpath.backend.service.port.withName("api"),

                /*
                    STELARAPI
                 */
                ingpath.withPath("/(stelar)(/|$)(.*)")
                + ingpath.withPathType("Prefix")
                + ingpath.backend.service.withName("stelarapi")
                + ingpath.backend.service.port.withName("apiserver-api"),

                /*
                    ONTOP
                 */
                ingpath.withPath("/(kg)(/|$)(.*)")
                + ingpath.withPathType("Prefix")
                + ingpath.backend.service.withName("ontop")
                + ingpath.backend.service.port.withName("ontop-ontop"),

            ])
        ])

        + ing.spec.withTls([
            k.networking.v1.ingressTLS.withHosts("stelar.vsamtuc.top")
            + k.networking.v1.ingressTLS.withSecretName("ckan-ui-tls")
        ])

}
