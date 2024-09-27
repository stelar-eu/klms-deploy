//
//  An ingress definition for STELAR deployments.
//

local k = import "k.libsonnet";

local ing = k.networking.v1.ingress;
local ingrule = k.networking.v1.ingressRule;
local ingpath = k.networking.v1.httpIngressPath;

{
    manifest(psm): {

        ingress: ing.new("stelar")
            + ing.metadata.withAnnotations({
                "cert-manager.io/cluster-issuer": "letsencrypt-production",
                "nginx.ingress.kubernetes.io/proxy-connect-timeout": "60s",
                "nginx.ingress.kubernetes.io/ssl-redirect": "true",
                "nginx.ingress.kubernetes.io/x-forwarded-prefix": "/$1",
                "nginx.ingress.kubernetes.io/rewrite-target": "/$3",
            })
            + ing.spec.withIngressClassName("nginx")
            + ing.spec.withRules([
                ingrule.withHost("tb.petrounetwork.gr")
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
                        MinIO
                     */
                    ingpath.withPath("/(s3)(/|$)(.*)")
                    + ingpath.withPathType("Prefix")
                    + ingpath.backend.service.withName("minio")
                    + ingpath.backend.service.port.withName("minio-minio"),

                    /*
                        Keycloak
                    */
                    ingpath.withPath("/(kc)(/|$)(.*)")
                    + ingpath.withPathType("Prefix")
                    + ingpath.backend.service.withName("keycloak")
                    + ingpath.backend.service.port.withName("keycloak-kc"),

                    /*
                        ONTOP
                    */
                    ingpath.withPath("/(kg)(/|$)(.*)")
                    + ingpath.withPathType("Prefix")
                    + ingpath.backend.service.withName("ontop")
                    + ingpath.backend.service.port.withName("ontop-ontop"),
                    
                    
                    ingpath.withPath("/(superset)(/|$)(.*)")
                    + ingpath.withPathType("Prefix")
                    + ingpath.backend.service.withName("superset")
                    + ingpath.backend.service.port.withName("superset-http"),

                ])
            ])

            + ing.spec.withTls([
                k.networking.v1.ingressTLS.withHosts(psm.endpoint.host)
                + k.networking.v1.ingressTLS.withSecretName("stelar-tls")
            ])

    }
}