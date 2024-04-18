/*
    Redis deployment and configuration.

    Redis is used both by CKAN and by Superset, mostly as a message queue.
*/
local k = import "k.libsonnet";

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


local PORT = import "stdports.libsonnet";


/*
    Superset seems to require v.7. Although CKAN specified v.6,
    there does not seem to be an issue.
 */
local REDIS_VERSION="7";
local REDIS_IMAGE_NAME = "redis:%s" % REDIS_VERSION;


/*********************
    The REDIS deployment.

    It requires
    (c) the deployment itself
 */

local redis_deployment(psm) = deploy.new(
   name="redis",
    containers = [
        container.new('redis', REDIS_IMAGE_NAME)
        //+ container.withEnvMap(ENV)

        + container.livenessProbe.exec.withCommand(
            ["/usr/local/bin/redis-cli", "-e", "QUIT"]
            )
        + container.livenessProbe.withInitialDelaySeconds(30)
        + container.livenessProbe.withPeriodSeconds(10)

        + container.readinessProbe.exec.withCommand(
            ["/usr/local/bin/redis-cli", "-e", "QUIT"]
            )
        + container.readinessProbe.withInitialDelaySeconds(30)
        + container.readinessProbe.withPeriodSeconds(10)

        // Expose 
        + container.withPorts([
            containerPort.newNamed(PORT.REDIS, "redis"),
        ])

    ],
    podLabels = {
        'app.kubernetes.io/name': 'data-catalog',
        'app.kubernetes.io/component': 'redis',
    }
)
;



{
    manifest(psm): {
        local redis_dep = redis_deployment(psm),
        redis: [
            redis_dep,
            svcs.serviceFor(redis_dep)
        ],
    }
}