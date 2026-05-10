// Core Ingress constructor for the ckan component.
local stelar_ingress = import "../../../util/stelar_ingress.libsonnet";

{
  new(config):
    stelar_ingress.new(
      "ckan",
      {
        "nginx.ingress.kubernetes.io/proxy-body-size": "5120m",
        "nginx.ingress.kubernetes.io/x-forwarded-prefix": "/$1",
        "nginx.ingress.kubernetes.io/rewrite-target": "/$3",
      },
      config.endpoint.PRIMARY_SUBDOMAIN,
      [
        ["/(dc)(/|$)(.*)", "ImplementationSpecific", "ckan", "api"],
      ],
      config
    ),
}
