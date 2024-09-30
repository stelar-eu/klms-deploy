local k = import "k.libsonnet";

local DBENV = import "dbenv.jsonnet";
local PORT = import "stdports.libsonnet";

#Liveness probe urls used by wait4x during init container(s) runtime.
local CKAN_URL = "http://ckan:%s/api/3/action/status_show" % PORT.CKAN;
local DB_URL = "postgresql://%(user)s:%(password)s@%(host)s/%(db)s?sslmode=disable" % {
                    user: DBENV.CKAN_DB_USER,
                    password: DBENV.CKAN_DB_PASSWORD,
                    host: "db",
                    db: DBENV.CKAN_DB
                };

local API_PORT = PORT.STELARAPI;

local API_ENV = {
    POSTGRES_HOST: DBENV.POSTGRES_HOST,
    POSTGRES_PORT: std.toString(PORT.PG),
    POSTGRES_USER: DBENV.CKAN_DB_USER,
    POSTGRES_PASSWORD: DBENV.CKAN_DB_PASSWORD,
    POSTGRES_DB: DBENV.CKAN_DB,

    SERVICE_PORT: std.toString(PORT.STELARAPI),
    CKAN_SITE_URL: "http://ckan:%d" % PORT.CKAN,
    SPARQL_ENDPOINT: "http://ontop:%d/sparql" % PORT.ONTOP,

    FLASK_APPLICATION_ROOT: "/stelar",

    // Note: this is not the actual API url, but instead it is the
    // URL sent to tool executions as hookup!
    API_URL: "http://stelarapi/",

    EXECUTION_ENGINE: "kubernetes",
};

{   
    API_ENV: API_ENV,
    CKAN_URL: CKAN_URL,
    DB_URL: DB_URL,    
    API_PORT: API_PORT,
}