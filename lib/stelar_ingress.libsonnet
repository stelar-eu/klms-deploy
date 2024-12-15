//
//  An ingress definition for STELAR deployments.
//

local k = import "k.libsonnet";

local ing = k.networking.v1.ingress;
local ingrule = k.networking.v1.ingressRule;
local ingpath = k.networking.v1.httpIngressPath;

{
    manifest(pim, config): {

        ingress_s3:  ing.new("s3")
            + ing.metadata.withAnnotations({
                "cert-manager.io/cluster-issuer": "letsencrypt-production",
                "nginx.ingress.kubernetes.io/proxy-connect-timeout": "60s",
                "nginx.ingress.kubernetes.io/ssl-redirect": "true",
                "nginx.ingress.kubernetes.io/proxy-body-size": "5120m",
                "nginx.ingress.kubernetes.io/proxy-http-version": "1.1",
                "nginx.ingress.kubernetes.io/proxy-chunked-transfer-encoding": "off",
                "nginx.ingress.kubernetes.io/proxy-set-header": "Host $http_host; X-Real-IP $remote_addr; X-Forwarded-For $proxy_add_x_forwarded_for; X-Forwarded-Proto $scheme;",
                "nginx.ingress.kubernetes.io/proxy-set-headers": "Connection '';",
            })
            + ing.spec.withIngressClassName("nginx")
            + ing.spec.withRules([
                ingrule.withHost(config.endpoint.MINIO_API_SUBDOMAIN+'.'+config.endpoint.ROOT_DOMAIN)
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
                k.networking.v1.ingressTLS.withHosts([config.endpoint.MINIO_API_SUBDOMAIN+'.'+config.endpoint.ROOT_DOMAIN])
                + k.networking.v1.ingressTLS.withSecretName(pim.namespace+"-tls"),
            ]),

        ingress_kc: ing.new("kc")
            + ing.metadata.withAnnotations({
                "cert-manager.io/cluster-issuer": "letsencrypt-production",
                "nginx.ingress.kubernetes.io/proxy-connect-timeout": "60s",
                "nginx.ingress.kubernetes.io/ssl-redirect": "true",
            })
            + ing.spec.withIngressClassName("nginx")
            + ing.spec.withRules([
                ingrule.withHost(config.endpoint.KEYCLOAK_SUBDOMAIN+'.'+config.endpoint.ROOT_DOMAIN)
                + ingrule.http.withPaths([                
                    ingpath.withPath("/")
                    + ingpath.withPathType("Prefix")
                    + ingpath.backend.service.withName("keycloak")
                    + ingpath.backend.service.port.withName("keycloak-kc"),
                ]),
            ])

            + ing.spec.withTls([
                k.networking.v1.ingressTLS.withHosts([config.endpoint.KEYCLOAK_SUBDOMAIN+'.'+config.endpoint.ROOT_DOMAIN])
                + k.networking.v1.ingressTLS.withSecretName(pim.namespace+"-tls"),
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

                ingrule.withHost(config.endpoint.PRIMARY_SUBDOMAIN+'.'+config.endpoint.ROOT_DOMAIN)
                + ingrule.http.withPaths([
                    /*
                        Root of the Ingress leads to / of STELAR API
                    */
                    ingpath.withPath("/")
                    + ingpath.withPathType("Prefix")
                    + ingpath.backend.service.withName("stelarapi")
                    + ingpath.backend.service.port.withName("apiserver-api"),
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
                k.networking.v1.ingressTLS.withHosts([config.endpoint.PRIMARY_SUBDOMAIN+'.'+config.endpoint.ROOT_DOMAIN])
                + k.networking.v1.ingressTLS.withSecretName(pim.namespace+"-tls"),
            ])

    }
}