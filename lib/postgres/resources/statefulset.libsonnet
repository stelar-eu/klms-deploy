// Core StatefulSet constructor for the db component.
local k = import "../../util/k.libsonnet";

local stateful = k.apps.v1.statefulSet;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;
local volumeMount = k.core.v1.volumeMount;
local vol = k.core.v1.volume;
local envSource = k.core.v1.envVarSource;

local db_config(config) = {
  POSTGRES_USER: config.postgres.POSTGRES_USER,
  POSTGRES_DB: config.postgres.POSTGRES_DEFAULT_DB,
  POSTGRES_HOST: config.postgres.POSTGRES_HOST,
  POSTGRES_PORT: std.toString(config.postgres.PORT),
  CKAN_DB_USER: config.postgres.CKAN_DB_USER,
  CKAN_DB: config.postgres.STELAR_DB,
  KEYCLOAK_DB_USER: config.postgres.KEYCLOAK_DB_USER,
  KEYCLOAK_DB: config.postgres.STELAR_DB,
  KEYCLOAK_DB_SCHEMA: config.postgres.KEYCLOAK_DB_SCHEMA,
  QUAY_DB_USER: config.postgres.QUAY_DB_USER,
  QUAY_DB: config.postgres.QUAY_DB,
  DATASTORE_READONLY_USER: config.postgres.DATASTORE_READONLY_USER,
  DATASTORE_DB: config.postgres.DATASTORE_DB,
};

{
  new(config):
    stateful.new(name = "db", containers = [
      container.new("postgis", config.postgres.IMAGE)
      + container.withImagePullPolicy("Always")
      + container.withEnvMap(db_config(config))
      + container.withEnvMap({
        PGDATA: config.postgres.PGDATA,
      })
      + container.withEnvMap({
        CKAN_DB_PASSWORD: envSource.secretKeyRef.withName(config.postgres.CKAN_DB_PASSWORD_SECRET_NAME) + envSource.secretKeyRef.withKey("password"),
        QUAY_DB_PASSWORD: envSource.secretKeyRef.withName(config.postgres.QUAY_DB_PASSWORD_SECRET_NAME) + envSource.secretKeyRef.withKey("password"),
        POSTGRES_PASSWORD: envSource.secretKeyRef.withName(config.postgres.POSTGRES_DB_PASSWORD_SECRET_NAME) + envSource.secretKeyRef.withKey("password"),
        KEYCLOAK_DB_PASSWORD: envSource.secretKeyRef.withName(config.postgres.KEYCLOAK_DB_PASSWORD_SECRET_NAME) + envSource.secretKeyRef.withKey("password"),
        DATASTORE_READONLY_PASSWORD: envSource.secretKeyRef.withName(config.postgres.DATASTORE_DB_PASSWORD_SECRET_NAME) + envSource.secretKeyRef.withKey("password"),
      })
      + container.withPorts([
        containerPort.newNamed(config.postgres.PORT, "psql"),
      ])
      + container.livenessProbe.exec.withCommand(["pg_isready", "-U", "postgres"])
      + container.livenessProbe.withInitialDelaySeconds(30)
      + container.livenessProbe.withPeriodSeconds(10)
      + container.withVolumeMounts([
        volumeMount.new("postgis-storage-vol", "/var/lib/postgresql/data", false),
      ]),
    ], podLabels = {
      "app.kubernetes.io/name": "data-catalog",
      "app.kubernetes.io/component": "postgis",
    })
    + stateful.spec.template.spec.withVolumes([
      vol.fromPersistentVolumeClaim("postgis-storage-vol", "postgis-storage"),
    ])
}
