//
//  An ingress definition for STELAR deployments.
//

local k = import "k.libsonnet";

local ing = k.networking.v1.ingress;
local ingrule = k.networking.v1.ingressRule;
local ingpath = k.networking.v1.httpIngressPath;

{
    manifest(pim, psm): {

        ingress_kc: ing.new("kc")
            + ing.metadata.withAnnotations({
                "cert-manager.io/cluster-issuer": "letsencrypt-production",
                "nginx.ingress.kubernetes.io/proxy-connect-timeout": "60s",
                "nginx.ingress.kubernetes.io/ssl-redirect": "true",
                "nginx.ingress.kubernetes.io/proxy-body-size": "5120m",
            })
            + ing.spec.withIngressClassName("nginx")
            + ing.spec.withRules([
                // ingrule.withHost("kc."+psm.endpoint.host)
                ingrule.withHost(psm.cluster.endpoint.KEYCLOAK_SUBDOMAIN+'.'+psm.cluster.endpoint.ROOT_DOMAIN)
                + ingrule.http.withPaths([                
                    ingpath.withPath("/")
                    + ingpath.withPathType("Prefix")
                    + ingpath.backend.service.withName("keycloak")
                    + ingpath.backend.service.port.withName("keycloak-kc"),
                ]),

                // ingrule.withHost("minio."+psm.endpoint.host)
                ingrule.withHost(psm.cluster.endpoint.MINIO_SUBDOMAIN+'.'+psm.cluster.endpoint.ROOT_DOMAIN)
                + ingrule.http.withPaths([

                    /*
                        MinIO API - Root Path "/"
                    */
                    ingpath.withPath("/")
                    + ingpath.withPathType("Prefix")
                    + ingpath.backend.service.withName("minio")
                    + ingpath.backend.service.port.withName("minio-minapi"),
                ]),
            ])

            + ing.spec.withTls([
                // k.networking.v1.ingressTLS.withHosts(["kc."+psm.endpoint.host])
                k.networking.v1.ingressTLS.withHosts([psm.cluster.endpoint.KEYCLOAK_SUBDOMAIN+'.'+psm.cluster.endpoint.ROOT_DOMAIN])
                + k.networking.v1.ingressTLS.withSecretName("kc-tls"),

                // k.networking.v1.ingressTLS.withHosts(["minio."+psm.endpoint.host])
                k.networking.v1.ingressTLS.withHosts([psm.cluster.endpoint.MINIO_SUBDOMAIN+'.'+psm.cluster.endpoint.ROOT_DOMAIN])
                + k.networking.v1.ingressTLS.withSecretName("minio-tls"),

            ]),

        ingress: ing.new("stelar")
            + ing.metadata.withAnnotations({
                "cert-manager.io/cluster-issuer": "letsencrypt-production",
                "nginx.ingress.kubernetes.io/proxy-connect-timeout": "60s",
                "nginx.ingress.kubernetes.io/ssl-redirect": "true",
                "nginx.ingress.kubernetes.io/x-forwarded-prefix": "/$1",
                "nginx.ingress.kubernetes.io/rewrite-target": "/$3",
                "nginx.ingress.kubernetes.io/proxy-body-size": "5120m",
            })
            + ing.spec.withIngressClassName("nginx")
            + ing.spec.withRules([

                // ingrule.withHost("klms."+psm.endpoint.host)
                ingrule.withHost(psm.cluster.endpoint.PRIMARY_SUBDOMAIN+'.'+psm.cluster.endpoint.ROOT_DOMAIN)
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
                        MinIO Console
                     */
                    ingpath.withPath("/(s3)(/|$)(.*)")
                    + ingpath.withPathType("Prefix")
                    + ingpath.backend.service.withName("minio")
                    + ingpath.backend.service.port.withName("minio-minio"),

                    /*
                        ONTOP
                    */
                    ingpath.withPath("/(kg)(/|$)(.*)")
                    + ingpath.withPathType("Prefix")
                    + ingpath.backend.service.withName("ontop")
                    + ingpath.backend.service.port.withName("ontop-ontop"),

                    /*
                        Superset
                    */
                    ingpath.withPath("/(superset)(/|$)(.*)")
                    + ingpath.withPathType("Prefix")
                    + ingpath.backend.service.withName("superset")
                    + ingpath.backend.service.port.withName("superset-http"),

                ]),
            ])

            + ing.spec.withTls([
                // k.networking.v1.ingressTLS.withHosts(["klms."+psm.endpoint.host])
                k.networking.v1.ingressTLS.withHosts([psm.cluster.endpoint.PRIMARY_SUBDOMAIN+'.'+psm.cluster.endpoint.ROOT_DOMAIN])
                + k.networking.v1.ingressTLS.withSecretName("stelar-tls"),
            ])

    }
}