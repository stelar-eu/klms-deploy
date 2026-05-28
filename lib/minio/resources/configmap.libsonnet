// Core ConfigMap constructor for the minio component.
local k = import "../../util/k.libsonnet";

local cmap = k.core.v1.configMap;

local minio_config(config) = {
  MINIO_ROOT_USER: config.minio.MINIO_ROOT_USER,
  MINIO_BROWSER_REDIRECT: config.minio.MINIO_BROWSER_REDIRECT,
  MINIO_BROWSER_REDIRECT_URL: config.SCHEME + "://" + config.PRIMARY_SUBDOMAIN + "." + config.ROOT_DOMAIN + "/s3",
  MINIO_IDENTITY_OPENID_REDIRECT_URI: config.SCHEME + "://" + config.PRIMARY_SUBDOMAIN + "." + config.ROOT_DOMAIN + "/s3",
};

{
  new(config):
    cmap.new("minio-cmap")
    + cmap.withData(minio_config(config))
}
