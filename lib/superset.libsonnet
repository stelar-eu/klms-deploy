/*
    Apache SUPERSET deployment and configuration as STELAR dashboard UI.

*/
local k = import "k.libsonnet";
//local util = import "github.com/grafana/jsonnet-libs/ksonnet-util/util.libsonnet";
local urllib = "urllib.libsonnet";

local podinit = import "podinit.libsonnet";
local pvol = import "pvolumes.libsonnet";
local svcs = import "services.libsonnet";


/* K8S API MODEL */
local deploy = k.apps.v1.deployment;
local stateful = k.apps.v1.statefulSet;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;
local servicePort = k.core.v1.servicePort;
local volumeMount = k.core.v1.volumeMount;
local pod = k.core.v1.pod;
local vol = k.core.v1.volume;
local service = k.core.v1.service;
local cm = k.core.v1.configMap;
local secret = k.core.v1.secret;
local envFrom = k.core.v1.envFromSource;

local psqlURI = "postgresql://%(user)s:%(password)s@%(host)s/%(db)s";


local PORT = import "stdports.libsonnet";
local DBENV = import "dbenv.jsonnet";

local ENV = {
    REDIS_HOST: "redis",
    REDIS_USER: "",
    REDIS_PORT: "6379",
    REDIS_PROTO: "redis",
    REDIS_DB: "4",
    REDIS_CELERY_DB: "5",
    DB_HOST: DBENV.POSTGRES_HOST,
    DB_PORT: DBENV.POSTGRES_PORT,
    DB_USER: DBENV.SUPERSET_USER,
    DB_PASS: DBENV.SUPERSET_PASSWORD,
    DB_NAME: DBENV.SUPERSET_DB,
};


local SUPERSET_IMAGE = 'apache/superset:4.0.0';
local DOCKERIZE_IMAGE = 'apache/superset:dockerize';

local DB_URL = psqlURI % {
    user: DBENV.SUPERSET_USER,
    password: DBENV.SUPERSET_PASSWORD,
    host: DBENV.POSTGRES_HOST,
    db: DBENV.SUPERSET_DB,
};

{

    local superset_deployment(psm) = deploy.new(
        'superset', 
        replicas=1, 
        containers=[
            container.new('superset', SUPERSET_IMAGE)
            + container.withCommand([
                "/bin/sh",
                "-c",
                ". /app/pythonpath/superset_bootstrap.sh; /usr/bin/run-server.sh"
            ])
            + container.withEnvMap({
                SUPERSET_PORT: std.toString(PORT.SUPERSET),
            })
            + container.withEnvFromMixin([
                envFrom.secretRef.withName("superset-env")
            ])
            + container.withVolumeMounts([
                volumeMount.new('superset-config', '/app/pythonpath', readOnly=true)
            ])
            + container.withPorts([
                containerPort.newNamed(PORT.SUPERSET, "http")
            ])

            + container.startupProbe.httpGet.withPath("/health")
            + container.startupProbe.httpGet.withPort("http")
            + container.startupProbe.withFailureThreshold(60)
            + container.startupProbe.withInitialDelaySeconds(15)
            + container.startupProbe.withPeriodSeconds(5)
            + container.startupProbe.withSuccessThreshold(1)
            + container.startupProbe.withTimeoutSeconds(1)

            + container.readinessProbe.httpGet.withPath("/health")
            + container.readinessProbe.httpGet.withPort("http")
            + container.readinessProbe.withFailureThreshold(3)
            + container.readinessProbe.withInitialDelaySeconds(15)
            + container.readinessProbe.withPeriodSeconds(15)
            + container.readinessProbe.withSuccessThreshold(1)
            + container.readinessProbe.withTimeoutSeconds(1)

            + container.livenessProbe.httpGet.withPath("/health")
            + container.livenessProbe.httpGet.withPort("http")
            + container.livenessProbe.withFailureThreshold(3)
            + container.livenessProbe.withInitialDelaySeconds(15)
            + container.livenessProbe.withPeriodSeconds(15)
            + container.livenessProbe.withSuccessThreshold(1)
            + container.livenessProbe.withTimeoutSeconds(1)

        ], 
        podLabels={
            app: 'usperset',
            'app.kubernetes.io/name': 'dashboards',
            'app.kubernetes.io/component': 'superset',
        }
    )
    + deploy.spec.template.spec.withInitContainers([
        podinit.wait4_postgresql("wait4-db", DB_URL + "?sslmode=disable"),
    ])
    + deploy.spec.template.spec.withVolumes([
        vol.fromSecret('superset-config', 'superset-config')
    ])
    ,


    local CFG_FILES={
        "superset_bootstrap.sh": importstr "../superset/superset_bootstrap.sh",
        "superset_init.sh": importstr "../superset/superset_init.sh",
        "superset_config.py": importstr "../superset/superset_config.py",
    }
    ,

    manifest(psm): {
        env: secret.new("superset-env", ENV, "Opaque"),
        config: secret.new("superset-config", CFG_FILES, "Opaque"),
        superset: superset_deployment(psm),
        service: svcs.serviceFor(self.superset
            /*, ignored_labels, nameFormat */)
    }
}
