// Ingress helper constructors shared across lib2 components.
local k = import "k.libsonnet";
local utils = import "utils.libsonnet";

local ing = k.networking.v1.ingress;
local ingrule = k.networking.v1.ingressRule;
local ingpath = k.networking.v1.httpIngressPath;
local ingtls = k.networking.v1.ingressTLS;

local standard_annotations = {
  "nginx.ingress.kubernetes.io/proxy-connect-timeout": "60s",
};

local https_annotations() = {
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

local https_ingress(name, annotations, host, paths, tls_name) =
  ing.new(name)
  + ing.metadata.withAnnotations(standard_annotations + https_annotations() + annotations)
  + ing.spec.withIngressClassName("nginx")
  + ing.spec.withRules(ingrule.withHost(host) + ingrule.http.withPaths(paths))
  + ing.spec.withTls([ingtls.withHosts([host]) + ingtls.withSecretName(tls_name)]);

local manual_tls_selected(config) =
  std.objectHas(config, "ingress")
  && std.objectHas(config.ingress, "tls")
  && std.member(config.ingress.tls, "manual_tls");

local manual_tls_secret_name(subdomain, config) =
  local manual_tls = config.ingress.manual_tls;
  if subdomain == config.PRIMARY_SUBDOMAIN then manual_tls.PRIMARY_TLS_SECRET_NAME
  else if subdomain == config.keycloak.SUBDOMAIN then manual_tls.KEYCLOAK_TLS_SECRET_NAME
  else if subdomain == config.minio.API_SUBDOMAIN then manual_tls.MINIO_API_TLS_SECRET_NAME
  else if subdomain == config.quay.SUBDOMAIN then manual_tls.REGISTRY_TLS_SECRET_NAME
  else error "manual_tls secret name is not configured for subdomain " + subdomain;

local tls_secret_name(subdomain, config) =
  if manual_tls_selected(config)
  then manual_tls_secret_name(subdomain, config)
  else utils.get_secret_name(subdomain, config.ROOT_DOMAIN);

{
  new(name, annotations, subdomain, paths, config):
    local host = subdomain + "." + config.ROOT_DOMAIN;
    if config.SCHEME == "http"
    then http_ingress(name, annotations, host, transform_paths(paths))
    else https_ingress(
      name,
      annotations,
      host,
      transform_paths(paths),
      tls_secret_name(subdomain, config)
    ),
}
