##########################################
## The Platform Independent Model ########
##########################################
# This structure contains parameters     #
# that wont change when deploying the    #
# cluster among different platforms.     #
##########################################


{
  ###########################
  ## TCP PORTS  #############
  ###########################
  ports: {
    CKAN: 5000,
    REDIS: 6379,
    SOLR: 8983,
    DATAPUSHER: 8800,
    PG: 5432,
    ONTOP: 8080,
    KEYCLOAK: 8080,
    STELARAPI: 80,
    SUPERSET: 8088,
    MINIO:9001,
    MINIOAPI:9000,
  },
  

  ###########################
  ## KEYCLOAK  ##############
  ###########################
  keycloak: {
    DB_TYPE: 'postgres',
    KEYCLOAK_ADMIN: 'admin',
    JDBC_PARAMS: 'useSsl=false',
    KC_HTTP_ENABLED: true,
    REALM: 'master',
  },
  
  
  ###########################
  ## DATABASE  ##############
  ###########################
  db:{
    POSTGRES_HOST: 'db',
    POSTGRES_PORT: self.ports.PG,
    POSTGRES_DEFAULT_DB: 'postgres',
    POSTGRES_USER: 'postgres',
    CKAN_DB_USER: 'ckan',
    STELAR_DB: 'stelar',
    KEYCLOAK_DB_USER: 'keycloak',
    KEYCLOAK_DB_SCHEMA: 'keycloak',
  },


  ###########################
  ## STELAR API  ############
  ###########################
  api: {
    FLASK_ROOT: '/stelar',
    KEYCLOAK_CLIENT_ID: 'stelarapi',
    EXEC_ENGINE: 'kubernetes',
    INTERNAL_URL: "http://stelarapi/",
  },


  ###########################
  ## MINIO  #################
  ###########################
  minio: {
    MINIO_ROOT_USER: 'root',
    MINIO_BROWSER_REDIRECT: "true",
  },
}