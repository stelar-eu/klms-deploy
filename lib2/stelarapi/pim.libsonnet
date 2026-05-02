{
  images: {
    API_IMAGE: 'petroud/stelar-api:prod',
  },

  labels: {
    'app.kubernetes.io/name': 'stelar-api',
    'app.kubernetes.io/component': 'stelarapi',
  },

  ports: {
    STELARAPI: 80,
    QUAY: 8080,
  },

  service: {
    account_name: 'stelarapi',
    port_name: 'api',
  },

  keycloak: {
    KC_API_CLIENT_NAME: 'stelar-api',
    ready_url: 'http://keycloak:9000/health/ready',
  },

  api: {
    FLASK_ROOT: '/stelar',
    EXEC_ENGINE: 'kubernetes',
    INTERNAL_URL: 'http://stelarapi/',
  },

  llm_search: {
    INTERNAL_URL: 'http://llmsearch:8000',
  },

  init: {
    wait_for_db_name: 'wait4-db',
    wait_for_ckan_name: 'wait4-ckan',
    wait_for_keycloak_name: 'wait4-keycloak',
  },
}
