/*
    ONTOP deployment and configuration as STELAR Knowledge Graph.

    This installation is based on the common database being set up
    correctly with the data schema.
*/

local k = import "k.libsonnet";
local util = import "github.com/grafana/jsonnet-libs/ksonnet-util/util.libsonnet";

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

local podinit = import "podinit.libsonnet";
local ONTOP_IMAGE_NAME = 'vsam/stelar-okeanos:ontop';

local DBENV = import "dbenv.jsonnet";
local PORT = import "stdports.libsonnet";

{

    base_container(name):: container.new(name, ONTOP_IMAGE_NAME)
        + container.withEnvMap({
            ONTOP_DB_USER: DBENV.CKAN_DB_USER,
            ONTOP_DB_PASSWORD: DBENV.CKAN_DB_PASSWORD,
            ONTOP_DB_URL: "jdbc:postgresql://db/ckan",
        })
        + container.withImagePullPolicy('Always')
    ,


    bootstrap_ctr:: self.base_container("ontop-bootstrap")
        + container.withCommand(['ontop', 'bootstrap',
            '--db-url', "jdbc:postgresql://db/ckan",
            '--db-user', DBENV.CKAN_DB_USER,
            '--db-password', DBENV.CKAN_DB_PASSWORD,
            '--db-driver', 'org.postgresql.Driver',
            '-b', 'http://klms.stelar-project.eu/',
            '-m', '/opt/ontop/input/klms-mappings.obda',
            '-t', '/opt/ontop/input/klms-ontology.ttl'
        ])
    ,

    local db_url = "postgresql://%(user)s:%(password)s@%(host)s/%(db)s?sslmode=disable" % {
        user: DBENV.CKAN_DB_USER,
        password: DBENV.CKAN_DB_PASSWORD,
        host: "db",
        db: DBENV.CKAN_DB
    },
    local ckan_url = "http://ckan:%s/api/3/action/status_show" % PORT.CKAN,

    deployment: deploy.new(
        "ontop",
        containers=[
            self.base_container("ontop")
            + container.withPorts([
                containerPort.newNamed(PORT.ONTOP, "ontop")                    
            ])
        ],
        podLabels = {
            'app.kubernetes.io/name': 'knowledge-graph',
            'app.kubernetes.io/component': 'ontop',
        }
    )

    + deploy.spec.template.spec.withInitContainers([

        /* We need to wait for ckan to be ready */
        //podinit.wait4_postgresql("wait4-db", ENV.CKAN_SQLALCHEMY_URL + "?sslmode=disable"),
        podinit.wait4_postgresql("wait4-db", db_url),
        podinit.wait4_http("wait4-ckan", ckan_url),

        /* Now we need to bootstrap the database */
        // Disabling bootstrap container
        // self.bootstrap_ctr
    ])
    ,

    svc: util.serviceFor(self.deployment)
}

