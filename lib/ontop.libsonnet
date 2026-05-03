/*
    ONTOP deployment and configuration as STELAR Knowledge Graph.

    This installation is based on the common database being set up
    correctly with the data schema.
*/

local k = import "k.libsonnet";
local util = import "github.com/grafana/jsonnet-libs/ksonnet-util/util.libsonnet";
local podinit = import "podinit.libsonnet";

local deploy = k.apps.v1.deployment;
local stateful = k.apps.v1.statefulSet;
local pvc = k.core.v1.persistentVolumeClaim;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;
local servicePort = k.core.v1.servicePort;
local volumeMount = k.core.v1.volumeMount;
local pod = k.core.v1.pod;
local vol = k.core.v1.volume;
local service = k.core.v1.service;
local cm = k.core.v1.configMap;
local secret = k.core.v1.secret;
local envSource = k.core.v1.envVarSource;

{
    manifest(pim, config): {

        base_container(name):: container.new(name, pim.images.ONTOP_IMAGE)
            + container.withEnvMap({
                ONTOP_DB_USER: pim.db.CKAN_DB_USER,
                ONTOP_DB_PASSWORD: envSource.secretKeyRef.withName(config.secrets.db.ckan_db_password_secret)+envSource.secretKeyRef.withKey("password"),
                ONTOP_DB_URL: "jdbc:postgresql://"+pim.db.POSTGRES_HOST+"/"+pim.db.STELAR_DB,
            })
            + container.withImagePullPolicy('Always')
        ,

        // local db_url = "postgresql://%(user)s:%(password)s@%(host)s/%(db)s?sslmode=disable" % {
        //     user: pim.db.CKAN_DB_USER,
        //     password: psm.db.CKAN_DB_PASSWORD,
        //     host: pim.db.POSTGRES_HOST,
        //     db: pim.db.STELAR_DB
        // },
        local ckan_url = "http://ckan:%s/api/3/action/status_show" % pim.ports.CKAN,

        deployment: deploy.new(
            "ontop",
            containers=[
                self.base_container("ontop")
                + container.withPorts([
                    containerPort.newNamed(pim.ports.ONTOP, "ontop")                    
                ])
                + container.withArgs(["start-ontop"])
            ],
            podLabels = {
                'app.kubernetes.io/name': 'knowledge-graph',
                'app.kubernetes.io/component': 'ontop',
            }
        )

        + deploy.spec.template.spec.withInitContainers([

            /* We need to wait for ckan to be ready */
            //podinit.wait4_postgresql("wait4-db", ENV.CKAN_SQLALCHEMY_URL + "?sslmode=disable"),
            podinit.wait4_postgresql("wait4-db", pim, config),
            podinit.wait4_http("wait4-ckan", ckan_url),
        ])
        ,

        svc: util.serviceFor(self.deployment)
    }

}
