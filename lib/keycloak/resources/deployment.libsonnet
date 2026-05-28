// Core Deployment constructor for the keycloak component.
local k = import "../../util/k.libsonnet";
local podinit = import "../../util/podinit.libsonnet";

local deploy = k.apps.v1.deployment;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;
local envSource = k.core.v1.envVarSource;

{
  new(config):
    deploy.new(name = "keycloak", containers = [
      container.new("keycloak", config.keycloak.IMAGE)
      + container.withEnvFrom([{
        configMapRef: {
          name: "kc-cmap",
        },
      }])
      + container.withEnvMap({
        KC_DB_PASSWORD: envSource.secretKeyRef.withName(config.postgres.KEYCLOAK_DB_PASSWORD_SECRET_NAME) + envSource.secretKeyRef.withKey("password"),
        KEYCLOAK_ADMIN_PASSWORD: envSource.secretKeyRef.withName(config.keycloak.KEYCLOAK_ROOT_PASSWORD_SECRET_NAME) + envSource.secretKeyRef.withKey("password"),
      })
      + container.withCommand(["/opt/keycloak/bin/kc.sh", "start", "--features=token-exchange,admin-fine-grained-authz"])
      + container.withPorts([
        containerPort.newNamed(config.keycloak.PORT, "kc"),
        containerPort.newNamed(9000, "kchealth"),
      ]),
    ], podLabels = {
      "app.kubernetes.io/name": "kc",
      "app.kubernetes.io/component": "keycloak",
    })
    + deploy.spec.template.spec.withInitContainers([
      podinit.wait4_postgresql("wait4-db", config),
    ])
}
