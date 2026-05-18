// Shared static model used by deployment-wide lib2 resources.
{
  namespace: 'stelar-lab',

  dynamic_volume_storage_class: 'csi-hostpath-sc',

  ports: {
    CKAN: 5000,
    SOLR: 8983,
    PG: 5432,
    REDIS: 6379,
    ONTOP: 8080,
    KEYCLOAK: 8080,
    STELARAPI: 80,
    KUBE_API: 443,
    DNS: 53,
  },

  db: {
    POSTGRES_HOST: 'db',
    CKAN_DB_USER: 'ckan',
    STELAR_DB: 'stelar',
    DATASTORE_DB: 'datastore',
    DATASTORE_READONLY_USER: 'datastore_ro',
    KEYCLOAK_DB_USER: 'keycloak',
    KEYCLOAK_DB_SCHEMA: 'keycloak',
    QUAY_DB_USER: 'quay',
    QUAY_DB: 'quay',
  },

  keycloak: {
    REALM: 'master',
    KEYCLOAK_ADMIN: 'admin',
    KC_API_CLIENT_NAME: 'stelar-api',
    KC_MINIO_CLIENT_NAME: 'minio',
    KC_CKAN_CLIENT_NAME: 'ckan',
  },

  minio: {
    MINIO_ROOT_USER: 'root',
  },

  policy: {
    name: 'stelar-task-isolation-policy',
    task_execution_class: 'task-execution',
    stelarapi_selector: 'stelarapi',
    kube_api_component: 'apiserver',
  },
}
