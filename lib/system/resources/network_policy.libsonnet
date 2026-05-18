// Core network-policy constructor for deployment-wide lib2 resources.
local k = import "../../util/k.libsonnet";

{
  new(config):
    k.networking.v1.networkPolicy.new("stelar-task-isolation-policy")
    + { metadata+: { namespace: config.namespace } }
    + {
      spec+: {
        podSelector: { matchLabels: { "stelar.metadata.class": "task-execution" } },
        policyTypes: ["Egress"],
        egress: [
          {
            to: [{ podSelector: { matchLabels: { app: "stelarapi" } } }],
            ports: [{ protocol: "TCP", port: config.api.PORT }],
          },
          {
            to: [{
              namespaceSelector: { matchLabels: { "kubernetes.io/metadata.name": "default" } },
              podSelector: { matchLabels: { component: "apiserver" } },
            }],
            ports: [{ protocol: "TCP", port: 443 }],
          },
          {
            to: [{ namespaceSelector: {} }],
            ports: [{ protocol: "UDP", port: 53 }],
          },
        ],
      },
    }
}
