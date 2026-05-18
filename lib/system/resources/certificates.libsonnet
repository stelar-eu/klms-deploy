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
    if config.SCHEME == "https" && config.CLUSTER_ISSUER != null then {
      [d + "_cert"]: cert.dns_certificate(
        name = utils.get_secret_name(d, config.ROOT_DOMAIN),
        issuerRef = cert.clusterIssuerRef(config.CLUSTER_ISSUER),
        dnsName = [d + "." + config.ROOT_DOMAIN]
      )
      for d in domains
    } else {}
}
