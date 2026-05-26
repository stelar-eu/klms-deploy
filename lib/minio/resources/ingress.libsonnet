// Core Ingress constructor for the minio component.
local stelar_ingress = import "../../util/stelar_ingress.libsonnet";

{
  new(config):
    stelar_ingress.new(
      "minio",
      {
        "nginx.ingress.kubernetes.io/proxy-body-size": "5120m",
        "nginx.ingress.kubernetes.io/proxy-http-version": "1.1",
      },
      config.minio.API_SUBDOMAIN,
      [
        ["/", "Prefix", "minio", "minio-minapi"],
      ],
      config
    )
}
