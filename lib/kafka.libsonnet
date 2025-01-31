
local k = import "k.libsonnet";
local pvol = import "pvolumes.libsonnet";
local svcs = import "services.libsonnet";
local PORT = import "stdports.libsonnet";

local deploy = k.apps.v1.deployment;
local container = k.core.v1.container;
local stateful = k.apps.v1.statefulSet;
local containerPort = k.core.v1.containerPort;
local pod = k.core.v1.pod;
local port = k.core.v1.containerPort;
local volumeMount = k.core.v1.volumeMount;
local vol = k.core.v1.volume;
local cmap = k.core.v1.configMap;
local service = k.core.v1.service;
local secret = k.core.v1.secret;
local podinit = import "podinit.libsonnet";
local envSource = k.core.v1.envVarSource;

{
    manifest(pim,config): {

        deployment: deploy.new(name="kafbat", containers=[
            container.new("kafbat", pim.images.KAFBAT_IMAGE)
            + container.withEnvMap({
                AUTH_TYPE: 'OAUTH2',
                AUTH_OAUTH2_CLIENT_KEYCLOAK_CLIENTID: pim.keycloak.KC_API_CLIENT_NAME,
                AUTH_OAUTH2_CLIENT_KEYCLOAK_CLIENTSECRET: envSource.secretKeyRef.withName(pim.keycloak.KC_API_CLIENT_NAME+"-client-secret")+envSource.secretKeyRef.withKey("secret"),
                AUTH_OAUTH2_CLIENT_KEYCLOAK_SCOPE: 'openid',
                'AUTH_OAUTH2_CLIENT_KEYCLOAK_ISSUER-URI': config.endpoint.SCHEME+"://" + config.endpoint.KEYCLOAK_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN + "/realms/" + pim.keycloak.REALM,
                'AUTH_OAUTH2_CLIENT_KEYCLOAK_REDIRECT-URI': config.endpoint.SCHEME+"://" + config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN + '/kafka/login/oauth2/code/keycloak',
                'AUTH_OAUTH2_CLIENT_KEYCLOAK_USER-NAME-ATTRIBUTE': 'preferred_username',
                'AUTH_OAUTH2_CLIENT_KEYCLOAK_CLIENT-NAME': 'STELAR SSO',
                AUTH_OAUTH2_CLIENT_KEYCLOAK_PROVIDER: 'keycloak',
                'AUTH_OAUTH2_CLIENT_KEYCLOAK_CUSTOM-PARAMS_TYPE': 'oauth',
                'AUTH_OAUTH2_CLIENT_KEYCLOAK_CUSTOM-PARAMS_LOGOUTURL': config.endpoint.SCHEME+"://" + config.endpoint.KEYCLOAK_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN + "/realms/" + pim.keycloak.REALM + '/protocol/openid-connect/logout',
                'AUTH_OAUTH2_CLIENT_KEYCLOAK_CUSTOM-PARAMS_ROLES-FIELD': 'realm_roles',
            })        
            + container.withPorts([
                containerPort.newNamed(pim.ports.KAFBAT, "kfb"),
            ])       
        ],
        podLabels={
            'app.kubernetes.io/name': 'kfb',
            'app.kubernetes.io/component': 'kafbat',
        }),

        kfb_svc: svcs.serviceFor(self.deployment),
    }
}