// Core certificate constructor for deployment-wide lib2 resources.
local cert = import "../../../util/certificate.libsonnet";
local utils = import "../../../util/utils.libsonnet";

{
  new(config):
    local domains = [
      config.endpoint.PRIMARY_SUBDOMAIN,
      config.endpoint.KEYCLOAK_SUBDOMAIN,
      config.endpoint.MINIO_API_SUBDOMAIN,
      config.endpoint.REGISTRY_SUBDOMAIN,
    ];
    if config.endpoint.SCHEME == "https" && config.endpoint.CLUSTER_ISSUER != null then {
      [d + "_cert"]: cert.dns_certificate(
        name = utils.get_secret_name(d, config.endpoint.ROOT_DOMAIN),
        issuerRef = cert.clusterIssuerRef(config.endpoint.CLUSTER_ISSUER),
        dnsName = [d + "." + config.endpoint.ROOT_DOMAIN]
      )
      for d in domains
    } else {},
}
