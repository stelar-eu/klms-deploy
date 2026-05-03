// Core network-policy constructor for deployment-wide lib2 resources.
local k = import "../../../util/k.libsonnet";
local pim = import "../../pim.libsonnet";

{
  new():
    k.networking.v1.networkPolicy.new(pim.policy.name)
    + { metadata+: { namespace: pim.namespace } }
    + {
      spec+: {
        podSelector: { matchLabels: { "stelar.metadata.class": pim.policy.task_execution_class } },
        policyTypes: ["Egress"],
        egress: [
          {
            to: [{ podSelector: { matchLabels: { app: pim.policy.stelarapi_selector } } }],
            ports: [{ protocol: "TCP", port: pim.ports.STELARAPI }],
          },
          {
            to: [{
              namespaceSelector: { matchLabels: { "kubernetes.io/metadata.name": "default" } },
              podSelector: { matchLabels: { component: pim.policy.kube_api_component } },
            }],
            ports: [{ protocol: "TCP", port: pim.ports.KUBE_API }],
          },
          {
            to: [{ namespaceSelector: {} }],
            ports: [{ protocol: "UDP", port: pim.ports.DNS }],
          },
        ],
      },
    },
}
