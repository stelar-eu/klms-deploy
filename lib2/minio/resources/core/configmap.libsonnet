local k = import "../../../util/k.libsonnet";
local pim = import "../../pim.libsonnet";
local system_pim = import "../../../system/pim.libsonnet";

local cmap = k.core.v1.configMap;

local minio_config(config) = {
  MINIO_ROOT_USER: system_pim.minio.MINIO_ROOT_USER,
  MINIO_BROWSER_REDIRECT: pim.minio.MINIO_BROWSER_REDIRECT,
  MINIO_BROWSER_REDIRECT_URL: config.endpoint.SCHEME + "://" + config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN + "/s3",
  MINIO_IDENTITY_OPENID_REDIRECT_URI: config.endpoint.SCHEME + "://" + config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN + "/s3",
};

{
  new(config):
    cmap.new("minio-cmap")
    + cmap.withData(minio_config(config)),
}
