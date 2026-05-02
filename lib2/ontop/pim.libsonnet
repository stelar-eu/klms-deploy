{
  images: {
    ONTOP_IMAGE: 'petroud/stelar-tuc:ontop',
  },

  labels: {
    'app.kubernetes.io/name': 'knowledge-graph',
    'app.kubernetes.io/component': 'ontop',
  },

  init: {
    wait_for_db_name: 'wait4-db',
    wait_for_ckan_name: 'wait4-ckan',
  },

  service: {
    port_name: 'ontop',
  },

  deployment: {
    image_pull_policy: 'Always',
    args: ['start-ontop'],
  },
}
