local k = import "k.libsonnet";

local networkPolicy(pim) =
  k.networking.v1.networkPolicy.new('stelar-task-isolation-policy') +
  { metadata+: { namespace: pim.namespace } } +
  {
    spec+: {
      podSelector: {
        matchLabels: {
          'stelar.metadata.class': 'task-execution',
        },
      },
      policyTypes: ['Egress'],
      egress: [
        // Allow egress to stelarapi pods in same namespace
        {
          to: [
            {
              podSelector: {
                matchLabels: {
                  app: 'stelarapi',
                },
              },
            },
          ],
          ports: [
            {
              protocol: 'TCP',
              port: 80,
            },
          ],
        },

        // Allow egress to Kubernetes API service (kubernetes.default.svc)
        {
          to: [
            {
              namespaceSelector: {
                matchLabels: {
                  'kubernetes.io/metadata.name': 'default',
                },
              },
              podSelector: {
                matchLabels: {
                  component: 'apiserver',
                },
              },
            },
          ],
          ports: [
            {
              protocol: 'TCP',
              port: 443,
            },
          ],
        },

        // Allow DNS resolution
        {
          to: [
            {
              namespaceSelector: {},
            },
          ],
          ports: [
            {
              protocol: 'UDP',
              port: 53,
            },
          ],
        },
      ],
    },
  };

{
  manifest(pim, config): networkPolicy(pim),
}
