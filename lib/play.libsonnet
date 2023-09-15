/*
    Deploying:
    - A postgresql service, with a database ready for keycloak realm.
    - Keycloak operator in this namespace.
    - Keycloak realm.
 */

local k = import "k.libsonnet";
local pg = import "postgresql.libsonnet";
local cert = import "certificate.libsonnet";

local playkc_credentials = {
  username: 'playkc',
  password: 'pl@ykc_st3l@r',
};

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
        },
        initdb: {
          scripts: {
            "create_kc_db.sql": |||
            CREATE USER %(username)s CREATEROLE LOGIN PASSWORD '%(password)s';
            CREATE DATABASE keycloak WITH OWNER %(username)s ENCODING 'utf8';
          ||| % playkc_credentials,
          }
        }
      }
    }
  });


local kc_op_manifest_yaml = importstr "../keycloak/kubernetes.yml";
local kc_op_manifest = std.parseYaml(kc_op_manifest_yaml);

local keycloak_inst = {

  /*
    TODO: restrict access to this secret
   */

  local playkc_cred1 = {
    username: std.base64(playkc_credentials.username),
    password: std.base64(playkc_credentials.password)
  },

  playkc_credentials_secret: k.core.v1.secret.new('playkc-credentials', playkc_cred1, 'Opaque'),


  /* Database configuration for KC instance */
  local play_cr_db = {
    vendor: 'postgres',
    host: 'postgres-postgresql.playground',
    port: 5432,
    database: 'keycloak',

    // These two below refer to the secret created right above.
    usernameSecret: {
      name: 'playkc-credentials',
      key: 'username'
    },
    passwordSecret: {
      name: 'playkc-credentials',
      key: 'password'
    },

    poolInitialSize: 1,
    poolMinSize: 2,
    poolMaxSize: 8,    
  },

  /* http configuration for KC instance */
  tls_cert_issuer: cert.selfSigned_issuer('play-cert-issuer-selfsigned'),

  tls_cert: cert.dns_certificate('play-kc-tls', 
        issuerRef=cert.issuerRef('play-cert-issuer-selfsigned'), 
        dnsName='skube07.vsamtuc.top',
        )
        {
          spec+: {
            /* Because this is a self-signed certificate, we need to add commonName... */
            commonName: 'selfsigned_kc',
            dnsNames+: ['skube08.vsamtuc.top']
          }
        }
        ,


  local play_cr_http = {
    tlsSecret: "play-kc-tls"
  },

  play_cr: {
      apiVersion: "k8s.keycloak.org/v2alpha1",
      kind: "Keycloak",
      metadata: {
        name: "play-kc"
      },
      spec: {
        db: play_cr_db,
        http: play_cr_http,
        
        // Hostnames can be set later...
        hostname: {
          hostname: 'skube07.vsamtuc.top',
          admin: 'skube08.vsamtuc.top',
          strict: false,
          strictBackchannel: false,
        },

        // Features: TBD
        features: {
          enabled: [
            'docker',
            'authorization'
          ],
          disabled: [
            'amdin',
            'step-up-authentication'
          ],
          // transaction: { xaEnabled: false }
        }
      }
  },



  play_realm: {
    apiVersion: "k8s.keycloak.org/v2alpha1",
    kind: "KeycloakRealmImport",
    metadata: {
      name: "play-realm-kc"
    },

    spec: {
      keycloakCRName: "play-kc",
      realm: {
        id: "play-realm",
        realm: "play-realm",
        displayName: "PlayRealm",
        enabled: true
      },
    },
  },
};



{
  keycloak_operator: kc_op_manifest,
  postgres: postgres,
  keycloak_realm: keycloak_inst,
}
