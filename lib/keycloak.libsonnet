
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


local KEYCLOAK_CONFIG = import "keycloakconfig.jsonnet";


{
    manifest(psm): {

        kc_cmap: cmap.new("kc-cmap")
                +cmap.withData(KEYCLOAK_CONFIG.ENV),


        deployment: deploy.new(name="keycloak", containers=[
            container.new("keycloak", psm.images.KEYCLOAK_IMAGE)
            + container.withEnvFrom([{
                configMapRef:{
                    name: "kc-cmap",
                },
            }])
            + container.withCommand(['/opt/keycloak/bin/kc.sh','start','--features=token-exchange,admin-fine-grained-authz'])
            + container.withPorts([
                containerPort.newNamed(PORT.KEYCLOAK, "kc")
            ])            
        ],
        podLabels={
        'app.kubernetes.io/name': 'kc',
        'app.kubernetes.io/component': 'keycloak',
        })
        + deploy.spec.template.spec.withInitContainers([
            /* We need to wait for ckan to be ready */
            podinit.wait4_postgresql("wait4-db", KEYCLOAK_CONFIG.DB_URL_PROBE),
        ]),

        kc_svc: svcs.serviceFor(self.deployment),
    }

}