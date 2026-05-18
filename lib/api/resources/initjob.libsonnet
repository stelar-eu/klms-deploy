// Core init-job constructor for the stelarapi component.
local k = import "../../util/k.libsonnet";
local podinit = import "../../util/podinit.libsonnet";
local images = import "../../util/imgutil.libsonnet";

local job = k.batch.v1.job;
local container = k.core.v1.container;
local volumeMount = k.core.v1.volumeMount;
local vol = k.core.v1.volume;
local envSource = k.core.v1.envVarSource;

{
  new(config):
    job.new("apiinit")
    + job.metadata.withLabels({
      "app.kubernetes.io/name": "api-init",
      "app.kubernetes.io/component": "apiinit",
    })
    + job.spec.template.spec.withContainers([
      local image = images.image_name(config.api.IMAGE);
      local pull_policy = images.pull_policy(config.api.IMAGE);

      container.new("apiinit-container", image)
      + container.withImagePullPolicy(pull_policy)
      + container.withArgs(["setup-db"])
      + container.withEnvMap({
        POSTGRES_HOST: config.postgres.POSTGRES_HOST,
        POSTGRES_DB: config.postgres.STELAR_DB,
        POSTGRES_USER: config.postgres.CKAN_DB_USER,
        POSTGRES_PASSWORD: envSource.secretKeyRef.withName(config.postgres.CKAN_DB_PASSWORD_SECRET_NAME) + envSource.secretKeyRef.withKey("password"),
        CKAN_ADMIN_TOKEN: envSource.secretKeyRef.withName("ckan-admin-token-secret") + envSource.secretKeyRef.withKey("token"),
      })
      + container.withVolumeMounts([
        volumeMount.new("ckan-ini", "/srv/stelar/config", false),
      ])
    ])
    + job.spec.template.spec.withInitContainers([
      podinit.wait4_postgresql("wait4-db", config),
    ])
    + job.spec.template.spec.withVolumes([
      vol.fromConfigMap("ckan-ini", "ckan-config", [{ key: "ckan.ini", path: "ckan.ini" }]),
    ])
    + job.spec.template.spec.withRestartPolicy("Never")
}
