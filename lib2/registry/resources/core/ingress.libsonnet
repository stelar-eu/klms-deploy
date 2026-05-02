local stelar_ingress = import "../../../util/stelar_ingress.libsonnet";

{
  new(config):
    stelar_ingress.new(
      "reg",
      {
        "nginx.ingress.kubernetes.io/proxy-body-size": "5120m",
      },
      config.endpoint.REGISTRY_SUBDOMAIN,
      [
        ["/", "Prefix", "quay", "quay-quay"],
        ["/v2/", "Prefix", "quay", "quay-quay"],
      ],
      config
    ),
}
