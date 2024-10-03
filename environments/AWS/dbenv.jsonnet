/*
    Various configuration options for the database.
 */
{
  //Postgres Default Database and User
  POSTGRES_USER: 'postgres',
  POSTGRES_PASSWORD: 'postgres',
  POSTGRES_DB: 'postgres',
  POSTGRES_HOST: 'db',
  POSTGRES_PORT: '5432',

  //CKAN schema in 'stelar' database, with user credentials
  CKAN_DB_USER: 'ckan',
  CKAN_DB_PASSWORD: 'ckan',
  CKAN_DB: 'stelar',
  
  //Keycloak schema in 'stelar' database, with user credentials 
  KEYCLOAK_DB_USER: 'keycloak',
  KEYCLOAK_DB_PASSWORD: 'keycloak',
  KEYCLOAK_DB: 'stelar',
  KEYCLOAK_DB_SCHEMA: 'keycloak',

  //CKAN modules schemata and databases
  DATASTORE_READONLY_USER: 'datastore_ro',
  DATASTORE_READONLY_PASSWORD: 'datastore',
  DATASTORE_DB: 'datastore',

  SUPERSET_USER: 'superset',
  SUPERSET_PASSWORD: 'superset',
  SUPERSET_DB: 'superset',
}
