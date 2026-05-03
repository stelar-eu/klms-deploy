// Core Deployment constructor for the keycloak component.
local k = import "../../../util/k.libsonnet";
local pim = import "../../pim.libsonnet";
local system_pim = import "../../../system/pim.libsonnet";
local podinit = import "../../../util/podinit.libsonnet";

local deploy = k.apps.v1.deployment;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;
local envSource = k.core.v1.envVarSource;

{
  new(config):
    deploy.new(name = "keycloak", containers = [
      container.new("keycloak", pim.images.KEYCLOAK_IMAGE)
      + container.withEnvFrom([{
        configMapRef: {
          name: "kc-cmap",
        },
      }])
      + container.withEnvMap({
        KC_DB_PASSWORD: envSource.secretKeyRef.withName(config.secrets.db.keycloak_db_passowrd_secret) + envSource.secretKeyRef.withKey("password"),
        KEYCLOAK_ADMIN_PASSWORD: envSource.secretKeyRef.withName(config.secrets.keycloak.root_password_secret) + envSource.secretKeyRef.withKey("password"),
      })
      + container.withCommand(pim.keycloak.command)
      + container.withPorts([
        containerPort.newNamed(system_pim.ports.KEYCLOAK, "kc"),
        containerPort.newNamed(pim.ports.HEALTH, "kchealth"),
      ]),
    ], podLabels = pim.labels)
    + deploy.spec.template.spec.withInitContainers([
      podinit.wait4_postgresql(pim.init.wait_for_db_name, system_pim, config),
    ]),
}
