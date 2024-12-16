/*
    Environment installs a docker-registry into the okeanos cluster.
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

local pvol = import "pvolumes.libsonnet";
local svc = import "services.libsonnet";

local tk_env = import "spec.json";


{
    _tk_env:: tk_env.spec,
    _config+:: {
        namespace: tk_env.spec.namespace,
        dynamicStorageClass: "longhorn",
        user: "admin",
        password: std.extVar("ADMIN_PASSWORD")
    },



    regcm: cm.new("registry",{
        'config.yml': |||
foo bar
|||
    })


    storage: pvol.pvcWithDynamicStorage("registry-claim", "60Gi"),

    regpod: pod.new("registry")
        + pod.metadata.withLabels({
            "app.kubernetes.io/name": "stelar",
            "app.kubernetes.io/component": "registry"
        })
        + pod.spec.withContainers([
            container.new("main", "registry:2")
            + container.withPorts(containerPort.newNamed("registry", 5000))
            + container.withVolumeMounts([
                volumeMount.new("registry", "/var/lib/registry", )
                //stateful.emptyVolumeMount("foo", "/opt")
            ])
            + container.withPorts([
                containerPort.newNamed(5000, "registry")
            ])
        ])
        + pod.spec.withVolumes([
            vol.fromPersistentVolumeClaim("registry", "registry-claim")
        ])
        + pod.spec.withRestartPolicy("Always")
    ,

    regsvc: svc.serviceForPod(self.regpod)
    ,


    local ing = k.networking.v1.ingress,
    local ingrule = k.networking.v1.ingressRule,
    local ingpath = k.networking.v1.httpIngressPath,

    reging: ing.new("registry")
        + ing.metadata.withAnnotations({
            //"cert-manager.io/cluster-issuer": "letsencrypt-production",
            "cert-manager.io/cluster-issuer": "letsencrypt-staging",
            "nginx.ingress.kubernetes.io/proxy-connect-timeout": "60s",
            "nginx.ingress.kubernetes.io/ssl-redirect": "true"
        })
        + ing.spec.withIngressClassName("nginx")
        + ing.spec.withRules([
            ingrule.withHost("registry.vsamtuc.top")
            + ingrule.http.withPaths([
                ingpath.withPath("/")
                + ingpath.withPathType("Prefix")
                + ingpath.backend.service.withName("registry")
                + ingpath.backend.service.port.withName("main-registry")
            ])
        ])

        + ing.spec.withTls([
            k.networking.v1.ingressTLS.withHosts("registry.vsamtuc.top")
            + k.networking.v1.ingressTLS.withSecretName("registry-tls")
        ])
        ,


}
