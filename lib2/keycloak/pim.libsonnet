// Static local model for the keycloak component.
{
  images: {
    KEYCLOAK_IMAGE: 'petroud/stelar-tuc:keycloak',
    KC_INIT: 'petroud/stelar-tuc:kcinit',
  },

  labels: {
    'app.kubernetes.io/name': 'kc',
    'app.kubernetes.io/component': 'keycloak',
  },

  ports: {
    HEALTH: 9000,
  },

  init: {
    wait_for_db_name: 'wait4-db',
  },

  keycloak: {
    DB_TYPE: 'postgres',
    KEYCLOAK_ADMIN: 'admin',
    JDBC_PARAMS: 'useSsl=false',
    KC_HTTP_ENABLED: 'true',
    KC_HEALTH_ENABLED: 'true',
    KC_HOSTNAME_BACKCHANNEL_DYNAMIC: 'true',
    command: ['/opt/keycloak/bin/kc.sh', 'start', '--features=token-exchange,admin-fine-grained-authz'],
  },
}
