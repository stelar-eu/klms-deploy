// Core Deployment constructor for the ontop component.
local k = import "../../util/k.libsonnet";
local podinit = import "../../util/podinit.libsonnet";

local deploy = k.apps.v1.deployment;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;
local envSource = k.core.v1.envVarSource;

local base_container(name, config) =
  container.new(name, config.ontop.IMAGE)
  + container.withEnvMap({
    ONTOP_DB_USER: config.postgres.CKAN_DB_USER,
    ONTOP_DB_PASSWORD: envSource.secretKeyRef.withName(config.postgres.CKAN_DB_PASSWORD_SECRET_NAME) + envSource.secretKeyRef.withKey("password"),
    ONTOP_DB_URL: "jdbc:postgresql://" + config.postgres.POSTGRES_HOST + "/" + config.postgres.STELAR_DB,
  })
  + container.withImagePullPolicy("Always");

{
  new(config):
    local ckan_url = "http://ckan:%s/api/3/action/status_show" % config.ckan.PORT;
    deploy.new(
      "ontop",
      containers = [
        base_container("ontop", config)
        + container.withPorts([
          containerPort.newNamed(config.ontop.PORT, "ontop"),
        ])
        + container.withArgs(["start-ontop"]),
      ],
      podLabels = {
        "app.kubernetes.io/name": "knowledge-graph",
        "app.kubernetes.io/component": "ontop",
      }
    )
    + deploy.spec.template.spec.withInitContainers([
      podinit.wait4_postgresql("wait4-db", config),
      podinit.wait4_http("wait4-ckan", ckan_url),
    ])
}
