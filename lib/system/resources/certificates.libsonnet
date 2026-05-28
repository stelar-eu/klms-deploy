// Core certificate constructor for deployment-wide lib2 resources.
local cert = import "../../util/certificate.libsonnet";
local utils = import "../../util/utils.libsonnet";

{
  new(config):
    local domains = [
      config.PRIMARY_SUBDOMAIN,
      config.keycloak.SUBDOMAIN,
      config.minio.API_SUBDOMAIN,
      config.quay.SUBDOMAIN,
    ];
    local ingress = if std.objectHas(config, "ingress") then config.ingress else {};
    local tls = if std.objectHas(ingress, "tls") then ingress.tls else [];
    local cluster_issuer =
      if std.member(tls, "cert_manager") && std.objectHas(ingress, "cert_manager")
      then ingress.cert_manager.ClusterIssuer
      else null;

    if config.SCHEME == "https" && cluster_issuer != null then {
      [d + "_cert"]: cert.dns_certificate(
        name = utils.get_secret_name(d, config.ROOT_DOMAIN),
        issuerRef = cert.clusterIssuerRef(cluster_issuer),
        dnsName = [d + "." + config.ROOT_DOMAIN]
      )
      for d in domains
    } else {}
}
