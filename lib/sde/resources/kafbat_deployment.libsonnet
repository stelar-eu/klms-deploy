// Core Deployment constructor for the Kafbat UI inside the sde component.
local k = import "../../util/k.libsonnet";
local podinit = import "../../util/podinit.libsonnet";

local deploy = k.apps.v1.deployment;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;
local envSource = k.core.v1.envVarSource;

{
  new(config):
    deploy.new(
      name = config.kafbat.deployment_name,
      containers = [
        container.new(config.kafbat.container_name, config.images.KAFBAT_IMAGE)
        + container.withImagePullPolicy(config.kafbat.image_pull_policy)
        + container.withEnvMap({
          AUTH_TYPE: config.kafbat.auth_type,
          AUTH_OAUTH2_CLIENT_KEYCLOAK_CLIENTID: config.keycloak.KC_API_CLIENT_NAME,
          AUTH_OAUTH2_CLIENT_KEYCLOAK_CLIENTSECRET: envSource.secretKeyRef.withName(config.keycloak.KC_API_CLIENT_NAME + "-client-secret") + envSource.secretKeyRef.withKey("secret"),
          AUTH_OAUTH2_CLIENT_KEYCLOAK_SCOPE: config.kafbat.keycloak_scope,
          "AUTH_OAUTH2_CLIENT_KEYCLOAK_ISSUER-URI": config.endpoint.SCHEME + "://" + config.endpoint.KEYCLOAK_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN + "/realms/" + config.keycloak.REALM,
          "AUTH_OAUTH2_CLIENT_KEYCLOAK_REDIRECT-URI": config.endpoint.SCHEME + "://" + config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN + config.kafbat.redirect_path,
          "AUTH_OAUTH2_CLIENT_KEYCLOAK_USER-NAME-ATTRIBUTE": config.kafbat.keycloak_user_name_attribute,
          "AUTH_OAUTH2_CLIENT_KEYCLOAK_CLIENT-NAME": config.kafbat.keycloak_client_name,
          AUTH_OAUTH2_CLIENT_KEYCLOAK_PROVIDER: config.kafbat.keycloak_provider,
          "AUTH_OAUTH2_CLIENT_KEYCLOAK_CUSTOM-PARAMS_TYPE": config.kafbat.keycloak_custom_params_type,
          KAFKA_CLUSTERS_0_NAME: config.kafbat.cluster_name,
          KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: config.kafka.broker_1_url + "," + config.kafka.broker_2_url,
          "AUTH_OAUTH2_CLIENT_KEYCLOAK_CUSTOM-PARAMS_LOGOUTURL": config.endpoint.SCHEME + "://" + config.endpoint.KEYCLOAK_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN + "/realms/" + config.keycloak.REALM + "/protocol/openid-connect/logout",
        })
        + container.withPorts([
          containerPort.newNamed(config.kafbat.port, config.kafbat.port_name),
        ]),
      ],
      podLabels = config.kafbat.labels
    )
    + deploy.spec.template.spec.withInitContainers([
      podinit.wait4_http(config.init.wait_for_keycloak_name, config.init.keycloak_ready_url),
    ]),
}
