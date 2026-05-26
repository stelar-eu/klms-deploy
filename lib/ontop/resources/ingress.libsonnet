// Core Ingress constructor for the Ontop component on the primary host.
local stelar_ingress = import "../../util/stelar_ingress.libsonnet";

{
  new(config):
    stelar_ingress.new(
      "kg",
      {
        "nginx.ingress.kubernetes.io/proxy-body-size": "5120m",
        "nginx.ingress.kubernetes.io/x-forwarded-prefix": "/$1",
        "nginx.ingress.kubernetes.io/rewrite-target": "/$3",
      },
      config.PRIMARY_SUBDOMAIN,
      [
        ["/(kg)(/|$)(.*)", "ImplementationSpecific", "ontop", "ontop-ontop"],
      ],
      config
    )
}
