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
    KC_HTTP_ENABLED: "true",
    KC_HEALTH_ENABLED: "true",
    REALM: 'master',
    KC_API_CLIENT_NAME: "stelar-api",
    KC_MINIO_CLIENT_NAME: "minio",
    KC_CKAN_CLIENT_NAME: "ckan"
  },
  
  
  ###########################
  ## DATABASE  ##############
  ###########################
  db:{
    POSTGRES_HOST: 'db',
    POSTGRES_PORT: 5432,
    POSTGRES_DEFAULT_DB: 'postgres',
    POSTGRES_USER: 'postgres',
    CKAN_DB_USER: 'ckan',
    STELAR_DB: 'stelar',
    DATASTORE_DB: 'datastore',
    DATASTORE_READONLY_USER: 'datastore_ro',
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
    MINIO_BROWSER_REDIRECT: 'true',
  },

  images: {
    API_IMAGE: 'petroud/stelar-tuc:data-api-prod',
    CKAN_IMAGE: 'petroud/stelar-tuc:ckan',
    POSTGIS_IMAGE:"petroud/stelar-tuc:postgres",
    MINIO_IMAGE:"quay.io/minio/minio:latest",
    ONTOP_IMAGE: "petroud/stelar-tuc:ontop",
    KEYCLOAK_IMAGE:"quay.io/keycloak/keycloak:25.0",
    REDIS_IMAGE:"redis:7",
    KC_INIT:"petroud/stelar-tuc:kcinit",   
  }

}