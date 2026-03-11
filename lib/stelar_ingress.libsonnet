local k = import "k.libsonnet";
local utils = import "utils.libsonnet"; // Import shared logic

local ing = k.networking.v1.ingress;
local ingrule = k.networking.v1.ingressRule;
local ingpath = k.networking.v1.httpIngressPath;
local ingtls = k.networking.v1.ingressTLS;

local standard_annotations = {
  "nginx.ingress.kubernetes.io/proxy-connect-timeout": "60s",
};

local letsencrypt_annotations(config) = {
  "cert-manager.io/cluster-issuer": config.endpoint.CLUSTER_ISSUER,
  "nginx.ingress.kubernetes.io/ssl-redirect": "true",
};

local transform_paths(paths) = [
  ingpath.withPath(p[0])
  + ingpath.withPathType(p[1])
  + ingpath.backend.service.withName(p[2])
  + ingpath.backend.service.port.withName(p[3])
  for p in paths
];

local http_ingress(name, annotations, host, paths) = 
  ing.new(name)
  + ing.metadata.withAnnotations(standard_annotations + annotations)
  + ing.spec.withIngressClassName("nginx")
  + ing.spec.withRules(ingrule.withHost(host) + ingrule.http.withPaths(paths));

local https_ingress_lets_encrypt(name, annotations, host, paths, tls_name, config) = 
  ing.new(name)
  + ing.metadata.withAnnotations(standard_annotations + letsencrypt_annotations(config) + annotations)
  + ing.spec.withIngressClassName("nginx")
  + ing.spec.withRules(ingrule.withHost(host) + ingrule.http.withPaths(paths))
  + ing.spec.withTls([ingtls.withHosts([host]) + ingtls.withSecretName(tls_name)]);

local ingress(pim, config, name, annotations, subdomain, paths) = 
  local host = subdomain + "." + config.endpoint.ROOT_DOMAIN;
  if (config.endpoint.SCHEME == 'http')
  then http_ingress(name, annotations, host, transform_paths(paths))
  else https_ingress_lets_encrypt(
    name, 
    annotations, 
    host, 
    transform_paths(paths), 
    utils.get_secret_name(subdomain, config.endpoint.ROOT_DOMAIN), // Call shared logic
    config
  );

{
  manifest(pim, config): {
    ingress_s3: ingress(pim, config, "s3", {
      "nginx.ingress.kubernetes.io/proxy-body-size": "5120m",
      "nginx.ingress.kubernetes.io/proxy-http-version": "1.1",
    }, config.endpoint.MINIO_API_SUBDOMAIN, [["/", "Prefix", "minio", "minio-minapi"]]),

    ingress_kc: ingress(pim, config, "kc", {}, config.endpoint.KEYCLOAK_SUBDOMAIN, [
      ["/", "Prefix", "keycloak", "keycloak-kc"]
    ]),

    ingress_reg: ingress(pim, config, "reg", {
      "nginx.ingress.kubernetes.io/proxy-body-size": "5120m",
    }, config.endpoint.REGISTRY_SUBDOMAIN, [
      ["/", "Prefix", "quay", "quay-quay"],
      ["/v2/", "Prefix", "quay", "quay-quay"],
    ]),

    ingress: ingress(pim, config, "stelar", {
      "nginx.ingress.kubernetes.io/proxy-body-size": "5120m",
    }, config.endpoint.PRIMARY_SUBDOMAIN, [
      ["/", "Prefix", "stelarapi", "apiserver-api"],
      ["/(dc)(/|$)(.*)", "ImplementationSpecific", "ckan", "api"],
      ["/(stelar)(/|$)(.*)", "ImplementationSpecific", "stelarapi", "apiserver-api"],
    ]),
  }
}