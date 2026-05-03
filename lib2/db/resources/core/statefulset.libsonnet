// Core StatefulSet constructor for the db component.
local k = import "../../../util/k.libsonnet";
local pim = import "../../pim.libsonnet";
local system_pim = import "../../../system/pim.libsonnet";

local stateful = k.apps.v1.statefulSet;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;
local volumeMount = k.core.v1.volumeMount;
local vol = k.core.v1.volume;
local envSource = k.core.v1.envVarSource;

local db_config() = {
  POSTGRES_USER: pim.db.POSTGRES_USER,
  POSTGRES_DB: pim.db.POSTGRES_DEFAULT_DB,
  POSTGRES_HOST: system_pim.db.POSTGRES_HOST,
  POSTGRES_PORT: std.toString(system_pim.ports.PG),
  CKAN_DB_USER: system_pim.db.CKAN_DB_USER,
  CKAN_DB: system_pim.db.STELAR_DB,
  KEYCLOAK_DB_USER: system_pim.db.KEYCLOAK_DB_USER,
  KEYCLOAK_DB: system_pim.db.STELAR_DB,
  KEYCLOAK_DB_SCHEMA: system_pim.db.KEYCLOAK_DB_SCHEMA,
  QUAY_DB_USER: pim.db.QUAY_DB_USER,
  QUAY_DB: pim.db.QUAY_DB,
  DATASTORE_READONLY_USER: system_pim.db.DATASTORE_READONLY_USER,
  DATASTORE_DB: system_pim.db.DATASTORE_DB,
};

{
  new(config):
    stateful.new(name = "db", containers = [
      container.new("postgis", pim.images.POSTGIS_IMAGE)
      + container.withImagePullPolicy(pim.deployment.image_pull_policy)
      + container.withEnvMap(db_config())
      + container.withEnvMap({
        PGDATA: pim.deployment.PGDATA,
      })
      + container.withEnvMap({
        CKAN_DB_PASSWORD: envSource.secretKeyRef.withName(config.secrets.db.ckan_db_password_secret) + envSource.secretKeyRef.withKey("password"),
        QUAY_DB_PASSWORD: envSource.secretKeyRef.withName(config.secrets.db.quay_db_password_secret) + envSource.secretKeyRef.withKey("password"),
        POSTGRES_PASSWORD: envSource.secretKeyRef.withName(config.secrets.db.postgres_db_password_secret) + envSource.secretKeyRef.withKey("password"),
        KEYCLOAK_DB_PASSWORD: envSource.secretKeyRef.withName(config.secrets.db.keycloak_db_passowrd_secret) + envSource.secretKeyRef.withKey("password"),
        DATASTORE_READONLY_PASSWORD: envSource.secretKeyRef.withName(config.secrets.db.datastore_db_password_secret) + envSource.secretKeyRef.withKey("password"),
      })
      + container.withPorts([
        containerPort.newNamed(system_pim.ports.PG, pim.service.port_name),
      ])
      + container.livenessProbe.exec.withCommand(pim.probes.liveness.command)
      + container.livenessProbe.withInitialDelaySeconds(pim.probes.liveness.initial_delay_seconds)
      + container.livenessProbe.withPeriodSeconds(pim.probes.liveness.period_seconds)
      + container.withVolumeMounts([
        volumeMount.new(pim.pvc.volume_name, pim.pvc.mount_path, false),
      ]),
    ], podLabels = pim.labels)
    + stateful.spec.template.spec.withVolumes([
      vol.fromPersistentVolumeClaim(pim.pvc.volume_name, pim.pvc.name),
    ]),
}
