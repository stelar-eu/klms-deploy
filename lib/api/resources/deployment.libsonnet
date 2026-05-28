// Core Deployment constructor for the stelarapi component.
local podinit = import "../../util/podinit.libsonnet";
local images = import "../../util/imgutil.libsonnet";
local k = import "../../util/k.libsonnet";

local deploy = k.apps.v1.deployment;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;
local envVar = k.core.v1.envVar;
local envSource = k.core.v1.envVarSource;

local ckan_url(config) =
  "http://ckan:%s/api/3/action/status_show" % config.ckan.PORT;

{
  new(config):
    deploy.new(
      name = "stelarapi",
      containers = [
        local image = images.image_name(config.api.IMAGE);
        local pull_policy = images.pull_policy(config.api.IMAGE);

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
          SMTP_PASSWORD: envSource.secretKeyRef.withName(config.api.SMTP_PASSWORD_SECRET_NAME) + envSource.secretKeyRef.withKey("password"),
          POSTGRES_PASSWORD: envSource.secretKeyRef.withName(config.postgres.CKAN_DB_PASSWORD_SECRET_NAME) + envSource.secretKeyRef.withKey("password"),
          KEYCLOAK_CLIENT_SECRET: envSource.secretKeyRef.withName(config.keycloak.KC_API_CLIENT_NAME + "-client-secret") + envSource.secretKeyRef.withKey("secret"),
          MINIO_ROOT_PASSWORD: envSource.secretKeyRef.withName(config.minio.MINIO_ROOT_PASSWORD_SECRET_NAME) + envSource.secretKeyRef.withKey("password"),
          CKAN_ADMIN_TOKEN: envSource.secretKeyRef.withName("ckan-admin-token-secret") + envSource.secretKeyRef.withKey("token"),
          SESSION_SECRET_KEY: envSource.secretKeyRef.withName(config.api.SESSION_SECRET_KEY_SECRET_NAME) + envSource.secretKeyRef.withKey("key"),
          CKAN_ENCODE_KEY: envSource.secretKeyRef.withName(config.ckan.CKAN_AUTH_SECRET_NAME) + envSource.secretKeyRef.withKey("jwt-key"),
          GROQ_API_KEY: if std.objectHas(config, "llm_search") then envSource.secretKeyRef.withName(config.llm_search.GROQ_API_KEY_SECRET_NAME) + envSource.secretKeyRef.withKey("key") else "none",
        })
        + container.withPorts([
          containerPort.newNamed(config.api.PORT, "api"),
        ]),
      ],
      podLabels = {
        "app.kubernetes.io/name": "api",
        "app.kubernetes.io/component": "stelarapi",
      }
    )
    + deploy.spec.template.spec.withInitContainers([
      podinit.wait4_postgresql("wait4-db", config),
      podinit.wait4_http("wait4-ckan", ckan_url(config)),
      podinit.wait4_http("wait4-keycloak", "http://keycloak:9000/health/ready"),
    ])
    + deploy.spec.template.spec.withServiceAccountName("stelarapi")
}
