/*
    Deploying:
    - A postgresql service, with a database ready for keycloak realm.
    - Keycloak operator in this namespace.
    - Keycloak realm.
 */


local pg = import "postgresql.libsonnet";

local postgres = pg.new({
    namespace:'playground',
    values: {
      auth: {
        postgresPassword: 'st3l@r',
        database: 'vsam',
        user: 'vsam',
        password: 'vsam_st3l@r'
      },
      primary: {
        persistence: { 
          size: '3Gi',
          storageClass: 'longhorn',
        }
      }
    }
  });


local kc_op_manifest_yaml = importstr "../keycloak/kubernetes.yml";
local kc_op_manifest = std.parseYaml(kc_op_manifest_yaml);

local keycloak_realm = {

  play_realm: {

  }

};



{
  keycloak_operator: kc_op_manifest,
  postgres: postgres,
  keycloak_realm: keycloak_realm,
}
