
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

// local db_url
// local KEYCLOAK_CONFIG = import "keycloakconfig.jsonnet";
local KEYCLOAK_CONFIG(pim,psm) = {
    local db_url = "jdbc:postgresql://%(host)s:%(port)s/stelar" % { 
                                                            host: pim.db.POSTGRES_HOST, 
                                                            port: pim.db.POSTGRES_PORT
                                                          },
    DB_URL_PROBE : "postgresql://%(user)s:%(password)s@%(host)s/%(db)s?sslmode=disable" % {
                    user: pim.db.CKAN_DB_USER,
                    password: psm.db.CKAN_DB_PASSWORD,
                    host: pim.db.POSTGRES_HOST,
                    db: pim.db.KEYCLOAK_DB
                },
    KC_DB: pim.keycloak.DB_TYPE,
    KC_DB_URL: db_url,
    KC_DB_USERNAME: psm.keycloak.KC_DB_USERNAME,
    KC_DB_PASSWORD: psm.keycloak.KC_DB_PASSWORD,
    KC_DB_SCHEMA: pim.keycloak.KC_DB_SCHEMA,
    KEYCLOAK_ADMIN: pim.keycloak.KEYCLOAK_ADMIN,
    KEYCLOAK_ADMIN_PASSWORD: psm.keycloak.KEYCLOAK_ADMIN_PASSWORD,
    KC_HOSTNAME: psm.keycloak.KC_HOSTNAME,
    KC_HOSTNAME_ADMIN: psm.keycloak.KC_HOSTNAME_ADMIN,
    // KC_HOSTNAME_DEBUG: "true",
    JDBC_PARAMS: pim.keycloak.JDBC_PARAMS,
    KC_HTTP_ENABLED: pim.keycloak.KC_HTTP_ENABLED,
    // KC_HEALTH_ENABLED: "true",
    // KC_METRICS_ENABLED: "true",
    
};

{
    manifest(pim,psm): {

        local keycloak_config = KEYCLOAK_CONFIG(pim, psm),

        kc_cmap: cmap.new("kc-cmap")
                // +cmap.withData(KEYCLOAK_CONFIG.ENV),
                   +cmap.withData(keycloak_config),

        deployment: deploy.new(name="keycloak", containers=[
            container.new("keycloak", psm.images.KEYCLOAK_IMAGE)
            + container.withEnvFrom([{
                configMapRef:{
                    name: "kc-cmap",
                },
            }])
            + container.withCommand(['/opt/keycloak/bin/kc.sh','start','--features=token-exchange,admin-fine-grained-authz'])
            + container.withPorts([
                // containerPort.newNamed(PORT.KEYCLOAK, "kc")
                containerPort.newNamed(pim.ports.KEYCLOAK, "kc")
            ])            
        ],
        podLabels={
        'app.kubernetes.io/name': 'kc',
        'app.kubernetes.io/component': 'keycloak',
        })
        + deploy.spec.template.spec.withInitContainers([
            /* We need to wait for ckan to be ready */
            // podinit.wait4_postgresql("wait4-db", KEYCLOAK_CONFIG.DB_URL_PROBE),
            podinit.wait4_postgresql("wait4-db", keycloak_config.DB_URL_PROBE),
        ]),

        kc_svc: svcs.serviceFor(self.deployment),
    }

}