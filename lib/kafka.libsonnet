
local k = import "k.libsonnet";
local pvol = import "pvolumes.libsonnet";
local svcs = import "services.libsonnet";
local PORT = import "stdports.libsonnet";

local deploy = k.apps.v1.deployment;
local container = k.core.v1.container;
local stateful = k.apps.v1.statefulSet;
local containerPort = k.core.v1.containerPort;
local pod = k.core.v1.pod;
local port = k.core.v1.containerPort;
local volumeMount = k.core.v1.volumeMount;
local vol = k.core.v1.volume;
local cmap = k.core.v1.configMap;
local service = k.core.v1.service;
local secret = k.core.v1.secret;
local podinit = import "podinit.libsonnet";
local envSource = k.core.v1.envVarSource;



local KAFKA_CONFIG(pim, brokerorder) = {
    ########################################
    ##  Kafka Node Configuration  ##########
    ##  - pim: The PIM from transform_pim ##
    ##  - brokerorder: The order of the   ##
    ##    broker in the cluster. (1,2,..) ##
    ########################################
    KAFKA_ZOOKEEPER_CONNECT: "localhost:"+pim.ports.ZOOKEEPER,
    KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: "INTERNAL:PLAINTEXT,EXTERNAL:PLAINTEXT",
    KAFKA_INTER_BROKER_LISTENER_NAME: "INTERNAL",
    KAFKA_LISTENERS: "INTERNAL://0.0.0.0:"+std.toString(pim.ports.KAFKA_INTERNAL+brokerorder-1)+",EXTERNAL://0.0.0.0:"+std.toString(brokerorder)+std.toString(pim.ports.KAFKA_INTERNAL),
    KAFKA_ADVERTISED_LISTENERS: "INTERNAL://localhost:"+std.toString(pim.ports.KAFKA_INTERNAL+brokerorder-1)+",EXTERNAL://kafka-cluster:"+std.toString(brokerorder)+std.toString(pim.ports.KAFKA_INTERNAL),
    KAFKA_BROKER_ID: std.toString(brokerorder),  
    KAFKA_MIN_INSYNC_REPLICAS: "1",
    KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: "2",  
};

{
    manifest(pim,config): {
        
        ########################################
        ##  KAFBAT UI  #########################
        ########################################
        deployment: deploy.new(name="kafbat", containers=[
            container.new("kafbat", pim.images.KAFBAT_IMAGE)
            + container.withImagePullPolicy("Always")
            + container.withEnvMap({
                AUTH_TYPE: 'OAUTH2',
                AUTH_OAUTH2_CLIENT_KEYCLOAK_CLIENTID: pim.keycloak.KC_API_CLIENT_NAME,
                AUTH_OAUTH2_CLIENT_KEYCLOAK_CLIENTSECRET: envSource.secretKeyRef.withName(pim.keycloak.KC_API_CLIENT_NAME+"-client-secret")+envSource.secretKeyRef.withKey("secret"),
                AUTH_OAUTH2_CLIENT_KEYCLOAK_SCOPE: 'openid',
                'AUTH_OAUTH2_CLIENT_KEYCLOAK_ISSUER-URI': config.endpoint.SCHEME+"://" + config.endpoint.KEYCLOAK_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN + "/realms/" + pim.keycloak.REALM,
                'AUTH_OAUTH2_CLIENT_KEYCLOAK_REDIRECT-URI': config.endpoint.SCHEME+"://" + config.endpoint.PRIMARY_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN + '/kafka/login/oauth2/code/keycloak',
                'AUTH_OAUTH2_CLIENT_KEYCLOAK_USER-NAME-ATTRIBUTE': 'preferred_username',
                'AUTH_OAUTH2_CLIENT_KEYCLOAK_CLIENT-NAME': 'STELAR SSO',
                AUTH_OAUTH2_CLIENT_KEYCLOAK_PROVIDER: 'keycloak',
                'AUTH_OAUTH2_CLIENT_KEYCLOAK_CUSTOM-PARAMS_TYPE': 'oauth',
                KAFKA_CLUSTERS_0_NAME: 'STELAR SDE Kafka Cluster',
                KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: pim.kafka.KAFKA_BROKER_1_URL+","+pim.kafka.KAFKA_BROKER_2_URL,
                'AUTH_OAUTH2_CLIENT_KEYCLOAK_CUSTOM-PARAMS_LOGOUTURL': config.endpoint.SCHEME+"://" + config.endpoint.KEYCLOAK_SUBDOMAIN + "." + config.endpoint.ROOT_DOMAIN + "/realms/" + pim.keycloak.REALM + '/protocol/openid-connect/logout'
            })        
            + container.withPorts([
                containerPort.newNamed(pim.ports.KAFBAT, "kfb"),
            ])       
        ],
        podLabels={
            'app.kubernetes.io/name': 'kfb',
            'app.kubernetes.io/component': 'kafbat',
        })
        + deploy.spec.template.spec.withInitContainers([
            /* We need to wait for Keycloak to be ready */
            podinit.wait4_http("wait4-keycloak", "http://keycloak:9000/health/ready"),
        ]),

        kfb_svc: svcs.serviceFor(self.deployment),


        ###########################################
        ##  KAFKA CLUSTER POD   ###################
        ###########################################
        ##  Kafka Cluster with 2 Brokers  1 ZK ####
        ###########################################
        kafka_cluster: deploy.new(name="kafka-cluster", containers=[
            
             container.new("kafka1", pim.images.KAFKA_IMAGE)
           + container.withImagePullPolicy("IfNotPresent")
           + container.withEnvMap(KAFKA_CONFIG(pim, 1))
           + container.withPorts([
                containerPort.newNamed(19092, "kf"),
           ]),

             container.new("kafka2", pim.images.KAFKA_IMAGE)
           + container.withImagePullPolicy("IfNotPresent")
           + container.withEnvMap(KAFKA_CONFIG(pim, 2))
           + container.withPorts([
                containerPort.newNamed(29092, "kf"),
           ]),
             
             container.new("zookeeper", pim.images.ZOOKEEPER_IMAGE)
           + container.withImagePullPolicy("IfNotPresent")
           + container.withEnvMap({
                ZOOKEEPER_CLIENT_PORT: std.toString(pim.ports.ZOOKEEPER),
                ZOOKEEPER_TICK_TIME: '2000',
                        
           })
           + container.withPorts([
                containerPort.newNamed(pim.ports.ZOOKEEPER, "zk"),
           ])
        ],
        podLabels={
            'app.kubernetes.io/name': 'kafka-cluster',
            'app.kubernetes.io/component': 'kafka',
        }),


        kafka_cluster_svc: svcs.serviceFor(self.kafka_cluster),
    }
}