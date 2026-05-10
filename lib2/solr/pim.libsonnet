// Static local model for the solr component.
{
  images: {
    SOLR_IMAGE: 'ckan/ckan-solr:2.10-solr9-spatial',
  },

  labels: {
    'app.kubernetes.io/name': 'data-catalog',
    'app.kubernetes.io/component': 'solr',
  },

  service: {
    name: 'solr',
    component: 'solr',
    port_name: 'solr',
  },

  pvc: {
    name: 'solr-data',
    size: '5Gi',
    volume_name: 'solr-storage-vol',
    mount_path: '/var/solr',
  },

  security: {
    allow_privilege_escalation: false,
    fs_group: 8983,
  },

  probes: {
    liveness: {
      command: ["/usr/bin/wget", "-qO", "/dev/null", "http://127.0.0.1:8983/solr/"],
      initial_delay_seconds: 120,
      period_seconds: 20,
      failure_threshold: 3,
      timeout_seconds: 45,
    },
    readiness: {
      command: ["/usr/bin/curl", "http://127.0.0.1:8983/solr/"],
      initial_delay_seconds: 120,
      period_seconds: 20,
      timeout_seconds: 45,
      failure_threshold: 5,
      success_threshold: 1,
    },
  },
}
