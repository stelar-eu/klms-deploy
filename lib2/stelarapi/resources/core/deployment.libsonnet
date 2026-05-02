local podinit = import "../../../util/podinit.libsonnet";
local images = import "../../../util/imgutil.libsonnet";
local k = import "../../../util/k.libsonnet";
local pim = import "../../pim.libsonnet";
local system_pim = import "../../../system/pim.libsonnet";

local deploy = k.apps.v1.deployment;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;
local envVar = k.core.v1.envVar;
local envSource = k.core.v1.envVarSource;

local ckan_url() =
  "http://ckan:%s/api/3/action/status_show" % system_pim.ports.CKAN;

{
  new(config):
    deploy.new(
      name = "stelarapi",
      containers = [
        local image = images.image_name(pim.images.API_IMAGE);
        local pull_policy = images.pull_policy(pim.images.API_IMAGE);

        container.new("apiserver", image)
        + container.withImagePullPolicy(pull_policy)
        + container.withEnvFrom([{
          configMapRef: {
            name: "api-config-map",
          },
        }])
        + container.withEnvMixin([
          envVar.fromFieldPath("API_NAMESPACE", "metadata.namespace"),
        ])
        + container.withEnvMap({
          SMTP_PASSWORD: envSource.secretKeyRef.withName(config.secrets.api.smtp_password_secret) + envSource.secretKeyRef.withKey("password"),
          POSTGRES_PASSWORD: envSource.secretKeyRef.withName(config.secrets.db.ckan_db_password_secret) + envSource.secretKeyRef.withKey("password"),
          KEYCLOAK_CLIENT_SECRET: envSource.secretKeyRef.withName(system_pim.keycloak.KC_API_CLIENT_NAME + "-client-secret") + envSource.secretKeyRef.withKey("secret"),
          MINIO_ROOT_PASSWORD: envSource.secretKeyRef.withName(config.secrets.minio.minio_root_password_secret) + envSource.secretKeyRef.withKey("password"),
          CKAN_ADMIN_TOKEN: envSource.secretKeyRef.withName("ckan-admin-token-secret") + envSource.secretKeyRef.withKey("token"),
          SESSION_SECRET_KEY: envSource.secretKeyRef.withName(config.secrets.api.session_secret_key) + envSource.secretKeyRef.withKey("key"),
          CKAN_ENCODE_KEY: envSource.secretKeyRef.withName(config.secrets.ckan.ckan_auth_secret) + envSource.secretKeyRef.withKey("jwt-key"),
          GROQ_API_KEY: if config.llm_search.ENABLE_LLM_SEARCH == "true" then envSource.secretKeyRef.withName(config.secrets.llm_search.groq_api_key_secret) + envSource.secretKeyRef.withKey("key") else "none",
        })
        + container.withPorts([
          containerPort.newNamed(pim.ports.STELARAPI, pim.service.port_name),
        ]),
      ],
      podLabels = pim.labels
    )
    + deploy.spec.template.spec.withInitContainers([
      podinit.wait4_postgresql(pim.init.wait_for_db_name, system_pim, config),
      podinit.wait4_http(pim.init.wait_for_ckan_name, ckan_url()),
      podinit.wait4_http(pim.init.wait_for_keycloak_name, pim.keycloak.ready_url),
    ])
    + deploy.spec.template.spec.withServiceAccountName(pim.service.account_name),
}
