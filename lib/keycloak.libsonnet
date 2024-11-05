
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

local HOSTNAME(config) = config.endpoint.SCHEME+"://"+config.endpoint.KEYCLOAK_SUBDOMAIN+"."+config.endpoint.ROOT_DOMAIN;

local KEYCLOAK_CONFIG(pim,config) = {
    local db_url = "jdbc:postgresql://%(host)s:%(port)s/stelar" % { 
                                                            host: pim.db.POSTGRES_HOST, 
                                                            port: pim.ports.PG
                                                          },
    KC_DB: pim.keycloak.DB_TYPE,
    KC_DB_URL: db_url,
    KC_DB_USERNAME: pim.db.KEYCLOAK_DB_USER,
    KC_DB_SCHEMA: pim.db.KEYCLOAK_DB_SCHEMA,
    KEYCLOAK_ADMIN: pim.keycloak.KEYCLOAK_ADMIN,
    KC_HOSTNAME: HOSTNAME(config),
    KC_HOSTNAME_ADMIN: HOSTNAME(config),
    JDBC_PARAMS: pim.keycloak.JDBC_PARAMS,
    KC_HTTP_ENABLED: pim.keycloak.KC_HTTP_ENABLED,    
    KC_HEALTH_ENABLED: pim.keycloak.KC_HEALTH_ENABLED,
};

{
    manifest(pim,config): {

        local keycloak_config = KEYCLOAK_CONFIG(pim, config),

        kc_cmap: cmap.new("kc-cmap")
                   +cmap.withData(keycloak_config),

        deployment: deploy.new(name="keycloak", containers=[
            container.new("keycloak", pim.images.KEYCLOAK_IMAGE)
            + container.withEnvFrom([{
                configMapRef:{
                    name: "kc-cmap",
                },
            }])
            + container.withEnvMap({
                KC_DB_PASSWORD: envSource.secretKeyRef.withName(config.secrets.db.keycloak_db_passowrd_secret)+envSource.secretKeyRef.withKey("password"),
                KEYCLOAK_ADMIN_PASSWORD: envSource.secretKeyRef.withName(config.secrets.keycloak.root_password_secret)+envSource.secretKeyRef.withKey("password"),
            })
            + container.withCommand(['/opt/keycloak/bin/kc.sh','start','--features=token-exchange,admin-fine-grained-authz'])
            + container.withPorts([
                containerPort.newNamed(pim.ports.KEYCLOAK, "kc"),
                containerPort.newNamed(9000, "kchealth")
            ])            
        ],
        podLabels={
        'app.kubernetes.io/name': 'kc',
        'app.kubernetes.io/component': 'keycloak',
        })
        + deploy.spec.template.spec.withInitContainers([
            podinit.wait4_postgresql("wait4-db", pim, config),
        ]),

        kc_svc: svcs.serviceFor(self.deployment),
    }

}