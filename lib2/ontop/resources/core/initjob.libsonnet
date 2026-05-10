// Core init-job constructor for the ontop component.
local k = import "../../../util/k.libsonnet";
local pim = import "../../pim.libsonnet";
local system_pim = import "../../../system/pim.libsonnet";
local podinit = import "../../../util/podinit.libsonnet";

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
      container.new("ontopinit-container", pim.images.ONTOP_IMAGE)
      + container.withImagePullPolicy("Always")
      + container.withArgs(["setup-db"])
      + container.withEnvMap({
        ONTOP_DB_USER: system_pim.db.CKAN_DB_USER,
        ONTOP_DB_PASSWORD: envSource.secretKeyRef.withName(config.secrets.db.ckan_db_password_secret) + envSource.secretKeyRef.withKey("password"),
        ONTOP_DB_HOST: system_pim.db.POSTGRES_HOST,
        ONTOP_DB: system_pim.db.STELAR_DB,
      })
      + container.withVolumeMounts([
        volumeMount.new("ckan-ini", "/srv/stelar/config", false),
      ])
    ])
    + job.spec.template.spec.withInitContainers([
      podinit.wait4_postgresql("wait4-db", system_pim, config),
    ])
    + job.spec.template.spec.withVolumes([
      vol.fromConfigMap("ckan-ini", "ckan-config", [{ key: "ckan.ini", path: "ckan.ini" }]),
    ])
    + job.spec.template.spec.withRestartPolicy("Never"),
}
