// Static local model for the ckan component.
{
  images: {
    CKAN_IMAGE: 'petroud/stelar-tuc:ckan',
  },

  name: 'ckan',

  labels: {
    'app.kubernetes.io/name': 'data-catalog',
    'app.kubernetes.io/component': 'ckan',
  },

  deployment: {
    replicas: 1,
    image_pull_policy: 'Always',
    args: ['start-server'],
  },

  service: {
    name: 'ckan',
    component: 'ckan',
    port_name: 'api',
  },

  config_volume: {
    name: 'ckan-ini',
    mount_path: '/srv/stelar/config',
    config_map_name: 'ckan-config',
    items: [{ key: 'ckan.ini', path: 'ckan.ini' }],
  },

  security: {
    allow_privilege_escalation: false,
    run_as_user: 92,
    run_as_group: 92,
    fs_group: 92,
  },

  keycloak: {
    KC_CKAN_CLIENT_NAME: 'ckan',
    redirect_path: '/dc/user/sso_login',
    button_style: '',
    enable_internal_login: 'True',
  },

  init: {
    wait_for_redis_name: 'wait4-redis',
    wait_for_db_name: 'wait4-db',
    wait_for_solr_name: 'wait4-solr',
    redis_url: 'redis://redis:6379/1',
    solr_service_name: 'solr',
    solr_path: '/solr/',
  },

  probes: {
    liveness: {
      status_path: '/api/3/action/status_show',
      initial_delay_seconds: 30,
      period_seconds: 60,
      timeout_seconds: 5,
      failure_threshold: 10,
    },
  },

  env: {
    CKAN_VERSION: '2.10.0',
    CKAN_PORT: '5000',
    CKAN_PORT_HOST: '5000',
    CKAN__ROOT_PATH: '/dc',
    CKAN_SITE_ID: 'default',
    CKAN_SYSADMIN_NAME: 'admin',
    CKAN_SYSADMIN_EMAIL: 'info@stelar.gr',
    CKAN_STORAGE_PATH: '/var/lib/ckan',
    CKAN_SMTP_SERVER: 'smtp.corporateict.domain:25',
    CKAN_SMTP_STARTTLS: 'True',
    CKAN_SMTP_USER: 'user',
    CKAN_SMTP_PASSWORD: 'pass',
    CKAN_SMTP_MAIL_FROM: 'ckan@localhost',
    CKAN__PLUGINS: 'envvars image_view text_view recline_view datastore datapusher'
      + ' keycloak'
      + ' resource_proxy geo_view'
      + ' spatial_metadata spatial_query',
    CKAN__HARVEST__MQ__TYPE: 'redis',
    CKAN__HARVEST__MQ__HOSTNAME: 'redis',
    CKAN__HARVEST__MQ__PORT: '6379',
    CKAN__HARVEST__MQ__REDIS_DB: '1',
    CKANEXT__SPATIAL__COMMON_MAP__TYPE: 'custom',
    CKANEXT__SPATIAL__COMMON_MAP__CUSTOM__URL: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    CKANEXT__SPATIAL__COMMON_MAP__ATTRIBUTION: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    TZ: 'UTC',
    CKAN_DATAPUSHER_URL: 'http://datapusher:8800',
    CKAN__DATAPUSHER__CALLBACK_URL_BASE: 'http://ckan:5000',
    DATAPUSHER_REWRITE_RESOURCES: 'True',
    DATAPUSHER_REWRITE_URL: 'http://ckan:5000',
    CKAN_SOLR_URL: 'http://solr:8983/solr/ckan',
    TEST_CKAN_SOLR_URL: 'http://solr:8983/solr/ckan',
    CKAN_REDIS_URL: 'redis://redis:6379/1',
    TEST_CKAN_REDIS_URL: 'redis://redis:6379/1',
  },
}
