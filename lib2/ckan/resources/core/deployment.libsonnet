// Core Deployment constructor for the ckan component.
local k = import "../../../util/k.libsonnet";
local pim = import "../../pim.libsonnet";
local system_pim = import "../../../system/pim.libsonnet";
local podinit = import "../../../util/podinit.libsonnet";

local deploy = k.apps.v1.deployment;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;
local volumeMount = k.core.v1.volumeMount;
local vol = k.core.v1.volume;
local envSource = k.core.v1.envVarSource;

local keycloak_config(config) = {
  CKANEXT__KEYCLOAK__SERVER_URL: config.endpoint.SCHEME + "://" + config.endpoint.KEYCLOAK_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN,
  CKANEXT__KEYCLOAK__CLIENT_ID: system_pim.keycloak.KC_CKAN_CLIENT_NAME,
  CKANEXT__KEYCLOAK__REALM_NAME: system_pim.keycloak.REALM,
  CKANEXT__KEYCLOAK__REDIRECT_URI: config.endpoint.SCHEME + "://" + config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN + pim.keycloak.redirect_path,
  CKANEXT__KEYCLOAK__BUTTON_STYLE: pim.keycloak.button_style,
  CKANEXT__KEYCLOAK__ENABLE_CKAN_INTERNAL_LOGIN: pim.keycloak.enable_internal_login,
};

{
  new(config):
    deploy.new(
      name = pim.name,
      replicas = pim.deployment.replicas,
      containers = [
        container.new(pim.name, pim.images.CKAN_IMAGE)
        + container.withImagePullPolicy(pim.deployment.image_pull_policy)
        + container.withEnvMap(pim.env + keycloak_config(config) + {
          CKAN_SITE_URL: config.endpoint.SCHEME + "://" + config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN,
          CKAN_SYSADMIN_PASSWORD: envSource.secretKeyRef.withName(config.secrets.ckan.ckan_admin_password_secret) + envSource.secretKeyRef.withKey("password"),
          CKANEXT__KEYCLOAK__CLIENT_SECRET_KEY: envSource.secretKeyRef.withName(system_pim.keycloak.KC_CKAN_CLIENT_NAME + "-client-secret") + envSource.secretKeyRef.withKey("secret"),
          CKAN___BEAKER__SESSION__SECRET: envSource.secretKeyRef.withName(config.secrets.ckan.ckan_auth_secret) + envSource.secretKeyRef.withKey("session-key"),
          CKAN___API_TOKEN__JWT__ENCODE__SECRET: envSource.secretKeyRef.withName(config.secrets.ckan.ckan_auth_secret) + envSource.secretKeyRef.withKey("jwt-key"),
          CKAN___API_TOKEN__JWT__DECODE__SECRET: envSource.secretKeyRef.withName(config.secrets.ckan.ckan_auth_secret) + envSource.secretKeyRef.withKey("jwt-key"),
          A_CKAN_DB_PASSWORD: envSource.secretKeyRef.withName(config.secrets.db.ckan_db_password_secret) + envSource.secretKeyRef.withKey("password"),
          A_DATASTORE_DB_PASSWORD: envSource.secretKeyRef.withName(config.secrets.db.datastore_db_password_secret) + envSource.secretKeyRef.withKey("password"),

          local _DB_HOST = { host: system_pim.db.POSTGRES_HOST },
          local _CKAN_U = _DB_HOST + { user: system_pim.db.CKAN_DB_USER, password: "$(A_CKAN_DB_PASSWORD)" },
          local _DS_U = _DB_HOST + { user: system_pim.db.DATASTORE_READONLY_USER, password: "$(A_DATASTORE_DB_PASSWORD)" },
          local psqlURI = "postgresql://%(user)s:%(password)s@%(host)s/%(db)s",

          CKAN_SQLALCHEMY_URL: psqlURI % (_CKAN_U + { db: system_pim.db.STELAR_DB }),
          CKAN_DATASTORE_WRITE_URL: psqlURI % (_CKAN_U + { db: system_pim.db.DATASTORE_DB }),
          CKAN_DATASTORE_READ_URL: psqlURI % (_DS_U + { db: system_pim.db.DATASTORE_DB }),
          TEST_CKAN_SQLALCHEMY_URL: self.CKAN_SQLALCHEMY_URL + "_test",
          TEST_CKAN_DATASTORE_WRITE_URL: self.CKAN_DATASTORE_WRITE_URL + "_test",
          TEST_CKAN_DATASTORE_READ_URL: self.CKAN_DATASTORE_READ_URL + "_test",
        })
        + container.livenessProbe.exec.withCommand(
          ["/usr/bin/curl", "--fail", "http://localhost:%s%s" % [system_pim.ports.CKAN, pim.probes.liveness.status_path]]
        )
        + container.livenessProbe.withInitialDelaySeconds(pim.probes.liveness.initial_delay_seconds)
        + container.livenessProbe.withPeriodSeconds(pim.probes.liveness.period_seconds)
        + container.livenessProbe.withTimeoutSeconds(pim.probes.liveness.timeout_seconds)
        + container.livenessProbe.withFailureThreshold(pim.probes.liveness.failure_threshold)
        + container.withPorts([
          containerPort.newNamed(system_pim.ports.CKAN, pim.service.port_name),
        ])
        + container.withArgs(pim.deployment.args)
        + container.withVolumeMounts([
          volumeMount.new(pim.config_volume.name, pim.config_volume.mount_path, false),
        ])
        + container.securityContext.withAllowPrivilegeEscalation(pim.security.allow_privilege_escalation),
      ],
      podLabels = pim.labels
    )
    + deploy.spec.template.spec.withInitContainers([
      podinit.wait4_redis(pim.init.wait_for_redis_name, pim.init.redis_url),
      podinit.wait4_postgresql(pim.init.wait_for_db_name, system_pim, config),
      podinit.wait4_http(
        pim.init.wait_for_solr_name,
        "http://%s:%s%s" % [pim.init.solr_service_name, system_pim.ports.SOLR, pim.init.solr_path]
      ),
    ])
    + deploy.spec.template.spec.withVolumes([
      vol.fromConfigMap(pim.config_volume.name, pim.config_volume.config_map_name, pim.config_volume.items),
    ])
    + deploy.spec.template.spec.securityContext.withRunAsUser(pim.security.run_as_user)
    + deploy.spec.template.spec.securityContext.withRunAsGroup(pim.security.run_as_group)
    + deploy.spec.template.spec.securityContext.withFsGroup(pim.security.fs_group),
}
