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

local psqlURI = "postgresql://%(user)s:%(password)s@%(host)s/%(db)s";


{
    manifest(psm): {

        


    }
}