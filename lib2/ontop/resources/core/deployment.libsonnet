local k = import "../../../util/k.libsonnet";
local pim = import "../../pim.libsonnet";
local system_pim = import "../../../system/pim.libsonnet";
local podinit = import "../../../util/podinit.libsonnet";

local deploy = k.apps.v1.deployment;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;
local envSource = k.core.v1.envVarSource;

local base_container(name, config) =
  container.new(name, pim.images.ONTOP_IMAGE)
  + container.withEnvMap({
    ONTOP_DB_USER: system_pim.db.CKAN_DB_USER,
    ONTOP_DB_PASSWORD: envSource.secretKeyRef.withName(config.secrets.db.ckan_db_password_secret) + envSource.secretKeyRef.withKey("password"),
    ONTOP_DB_URL: "jdbc:postgresql://" + system_pim.db.POSTGRES_HOST + "/" + system_pim.db.STELAR_DB,
  })
  + container.withImagePullPolicy(pim.deployment.image_pull_policy);

{
  new(config):
    local ckan_url = "http://ckan:%s/api/3/action/status_show" % system_pim.ports.CKAN;
    deploy.new(
      "ontop",
      containers = [
        base_container("ontop", config)
        + container.withPorts([
          containerPort.newNamed(system_pim.ports.ONTOP, pim.service.port_name),
        ])
        + container.withArgs(pim.deployment.args),
      ],
      podLabels = pim.labels
    )
    + deploy.spec.template.spec.withInitContainers([
      podinit.wait4_postgresql(pim.init.wait_for_db_name, system_pim, config),
      podinit.wait4_http(pim.init.wait_for_ckan_name, ckan_url),
    ]),
}
