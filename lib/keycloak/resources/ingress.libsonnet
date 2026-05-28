// Core Ingress constructor for the keycloak component.
local stelar_ingress = import "../../util/stelar_ingress.libsonnet";

{
  new(config):
    stelar_ingress.new(
      "kc",
      {
        "nginx.ingress.kubernetes.io/proxy-body-size": "5120m",
      },
      config.keycloak.SUBDOMAIN,
      [
        ["/", "Prefix", "keycloak", "keycloak-kc"],
      ],
      config
    )
}
