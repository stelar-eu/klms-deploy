local k = import "k.libsonnet";
local DBENV = import "dbenv.jsonnet";


local db_url = "jdbc:postgresql://%(host)s:%(port)s/ckan" % { 
                                                            host: DBENV.POSTGRES_HOST, 
                                                            port: DBENV.POSTGRES_PORT
                                                          };

local ENV = {
    KC_DB: "postgres",
    KC_DB_URL: db_url,
    KC_DB_USERNAME: "ckan",
    KC_DB_PASSWORD: "ckan",
    KC_DB_SCHEMA: "keycloak",
    KEYCLOAK_ADMIN: "admin",
    KEYCLOAK_ADMIN_PASSWORD: "stelartuc",
    KC_HOSTNAME_STRICT:"true",
    KC_HOSTNAME: "https://tb.petrounetwork.gr/kc",
    KC_HOSTNAME_ADMIN: "https://tb.petrounetwork.gr/kc/",
    KC_HOSTNAME_DEBUG: "true",
    KC_HOSTNAME_BACKCHANNEL_DYNAMIC: "true",
    JDBC_PARAMS: "useSsl=false",
    KC_HTTP_ENABLED: "true",
    KC_HEALTH_ENABLED: "true",
    KC_METRICS_ENABLED: "true",
};


{   
    ENV: ENV,
}