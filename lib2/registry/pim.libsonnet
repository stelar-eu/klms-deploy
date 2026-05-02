{
  images: {
    REGISTRY_IMAGE: 'petroud/stelar-tuc:registry',
    REGISTRY_INIT: 'petroud/stelar-tuc:registry-init',
  },

  labels: {
    'app.kubernetes.io/name': 'quay',
    'app.kubernetes.io/component': 'quay',
  },

  ports: {
    QUAY: 8080,
  },

  deployment: {
    image_pull_policy: 'Always',
  },

  config_volume: {
    name: 'quay-conf',
    config_map_name: 'registry-config',
    mount_path: '/quay-registry/conf/stack',
    items: [{ key: 'config.yaml', path: 'config.yaml' }],
  },

  registry: {
    QUAY_PULLERS_ROLE: 'pullers',
    QUAY_PUSHERS_ROLE: 'pushers',
    KC_ROLES_CLAIM: 'groups',
    MINIO_BUCKET: 'registry',
  },
}
