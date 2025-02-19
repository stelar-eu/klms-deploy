local k = import "k.libsonnet";
local DBENV = import "dbenv.jsonnet";


local db_url = "jdbc:postgresql://%(host)s:%(port)s/stelar" % { 
                                                            host: DBENV.POSTGRES_HOST, 
                                                            port: DBENV.POSTGRES_PORT
                                                          };
local DB_URL_PROBE = "postgresql://%(user)s:%(password)s@%(host)s/%(db)s?sslmode=disable" % {
                    user: DBENV.CKAN_DB_USER,
                    password: DBENV.CKAN_DB_PASSWORD,
                    host: "db",
                    db: DBENV.KEYCLOAK_DB
                };
local ENV = {
    KC_DB: "postgres",
    KC_DB_URL: db_url,
    KC_DB_USERNAME: "keycloak",
    KC_DB_PASSWORD: "keycloak",
    KC_DB_SCHEMA: "keycloak",
    KEYCLOAK_ADMIN: "admin",
    KEYCLOAK_ADMIN_PASSWORD: "stelartuc",
    KC_HOSTNAME: "https://kc.petrounetwork.gr",
    KC_HOSTNAME_ADMIN: "https://kc.petrounetwork.gr",
    KC_HOSTNAME_DEBUG: "true",
    JDBC_PARAMS: "useSsl=false",
    KC_HTTP_ENABLED: "true",
    KC_HEALTH_ENABLED: "true",
    KC_METRICS_ENABLED: "true",
};


{   
    ENV: ENV,
    DB_URL_PROBE: DB_URL_PROBE,
}