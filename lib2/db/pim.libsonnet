{
  images: {
    POSTGIS_IMAGE: 'petroud/stelar-tuc:postgres',
  },

  labels: {
    'app.kubernetes.io/name': 'data-catalog',
    'app.kubernetes.io/component': 'postgis',
  },

  pvc: {
    name: 'postgis-storage',
    size: '5Gi',
    volume_name: 'postgis-storage-vol',
    mount_path: '/var/lib/postgresql/data',
  },

  service: {
    name: 'db',
    component: 'postgis',
    port_name: 'psql',
  },

  deployment: {
    image_pull_policy: 'Always',
    PGDATA: '/var/lib/postgresql/data/pgdata',
  },

  probes: {
    liveness: {
      command: ['pg_isready', '-U', 'postgres'],
      initial_delay_seconds: 30,
      period_seconds: 10,
    },
  },

  db: {
    POSTGRES_USER: 'postgres',
    POSTGRES_DEFAULT_DB: 'postgres',
    QUAY_DB_USER: 'quay',
    QUAY_DB: 'quay',
  },
}
