local k = import "k.libsonnet";
local cert = import "certificate.libsonnet";
local utils = import "utils.libsonnet";


local networkPolicy(pim) =
  k.networking.v1.networkPolicy.new('stelar-task-isolation-policy') +
  { metadata+: { namespace: pim.namespace } } +
  {
    spec+: {
      podSelector: { matchLabels: { 'stelar.metadata.class': 'task-execution' } },
      policyTypes: ['Egress'],
      egress: [
        { to: [{ podSelector: { matchLabels: { app: 'stelarapi' } } }], ports: [{ protocol: 'TCP', port: 80 }] },
        { to: [{ namespaceSelector: { matchLabels: { 'kubernetes.io/metadata.name': 'default' } }, podSelector: { matchLabels: { component: 'apiserver' } } }], ports: [{ protocol: 'TCP', port: 443 }] },
        { to: [{ namespaceSelector: {} }], ports: [{ protocol: 'UDP', port: 53 }] },
      ],
    },
  };

{
  manifest(pim, config): 
    // Move 'local' definitions here, before the opening brace of the object
    local domains = [
        config.endpoint.PRIMARY_SUBDOMAIN,
        config.endpoint.KEYCLOAK_SUBDOMAIN,
        config.endpoint.MINIO_API_SUBDOMAIN,
        config.endpoint.REGISTRY_SUBDOMAIN,
    ]; 
    {
      policy: networkPolicy(pim),
    } + // ONLY generate certs if we are actually using HTTPS!
    (if config.endpoint.SCHEME == 'https' && config.endpoint.CLUSTER_ISSUER != null then {
      [d + "_cert"]: cert.dns_certificate(
          name=utils.get_secret_name(d, config.endpoint.ROOT_DOMAIN),
          issuerRef=cert.clusterIssuerRef(config.endpoint.CLUSTER_ISSUER),
          dnsName=[d + "." + config.endpoint.ROOT_DOMAIN]
      ) for d in domains
    } else {})
}