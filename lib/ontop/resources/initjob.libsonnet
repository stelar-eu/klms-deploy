// Core init-job constructor for the ontop component.
local k = import "../../util/k.libsonnet";
local podinit = import "../../util/podinit.libsonnet";

local job = k.batch.v1.job;
local container = k.core.v1.container;
local volumeMount = k.core.v1.volumeMount;
local vol = k.core.v1.volume;
local envSource = k.core.v1.envVarSource;

{
  new(config):
    job.new("ontopinit")
    + job.metadata.withLabels({
      "app.kubernetes.io/name": "ontop-init",
      "app.kubernetes.io/component": "ontopinit",
    })
    + job.spec.template.spec.withContainers([
      container.new("ontopinit-container", config.ontop.IMAGE)
      + container.withImagePullPolicy("Always")
      + container.withArgs(["setup-db"])
      + container.withEnvMap({
        ONTOP_DB_USER: config.postgres.CKAN_DB_USER,
        ONTOP_DB_PASSWORD: envSource.secretKeyRef.withName(config.postgres.CKAN_DB_PASSWORD_SECRET_NAME) + envSource.secretKeyRef.withKey("password"),
        ONTOP_DB_HOST: config.postgres.POSTGRES_HOST,
        ONTOP_DB: config.postgres.STELAR_DB,
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
