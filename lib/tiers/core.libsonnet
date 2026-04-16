local systeminit = import 'systeminit.libsonnet';

{
  images: {
    API_IMAGE: 'petroud/stelar-api:prod',
    CKAN_IMAGE: 'petroud/stelar-tuc:ckan',
    POSTGIS_IMAGE: 'petroud/stelar-tuc:postgres',
    MINIO_IMAGE: 'quay.io/minio/minio:RELEASE.2025-04-22T22-12-26Z-cpuv1',
    KEYCLOAK_IMAGE: 'petroud/stelar-tuc:keycloak',
    REDIS_IMAGE: 'redis:7',
    KC_INIT: 'petroud/stelar-tuc:kcinit',
  },

  baseComponents:: [
    import 'db.libsonnet',
    import 'redis.libsonnet',
    import 'minio.libsonnet',
    import 'keycloak.libsonnet',
    import 'stelarapi.libsonnet',
    import 'ckan.libsonnet',
    import 'stelar_ingress.libsonnet',
    import 'network.libsonnet',
  ],

  components: self.baseComponents + [
    systeminit('core'),
  ],
}
