local k = import "k.libsonnet";
local svcs = import "services.libsonnet";
local pvol = import "pvolumes.libsonnet";


local deploy = k.apps.v1.deployment;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;
local envSource = k.core.v1.envVarSource;
local volumeMount = k.core.v1.volumeMount;
local vol = k.core.v1.volume;

{
    manifest(pim,config): {

        pvc_chroma_storage:  pvol.pvcWithDynamicStorage(
            "chroma-storage",
            "5Gi",
            pim.dynamic_volume_storage_class,),

        deployment: deploy.new(name="llmsearch", containers=[
            ################################################
            ## Semantic Dataset Search CONTAINER ###########
            ## Listens on: 8080  ###########################
            ################################################
            container.new("llmsearch", pim.images.LLM_SEARCH_IMAGE)
            + container.withImagePullPolicy("Always")
            + container.withEnvMap({
                GROQ_URL: config.llm_search.GROQ_API_URL,
                GROQ_API_KEY: envSource.secretKeyRef.withName(config.secrets.llm_search.groq_api_key_secret)+envSource.secretKeyRef.withKey("key"),
                GROQ_MODEL: config.llm_search.GROQ_MODEL,
                LLM_OPTION: "groq",
                CHROMA_DIR: "/app/chroma",
                REDIS_URL: "redis://redis:"+pim.ports.REDIS+"/5"
            })
            + container.withPorts([
                containerPort.newNamed(pim.ports.LLM_SEARCH, "api"),
            ])
            + container.withVolumeMounts([
                volumeMount.new("chroma-storage-vol", "/app/chroma", false),
            ]),
        ],
        podLabels={
            'app.kubernetes.io/name': 'llmsearch',
            'app.kubernetes.io/component': 'llmsearch',
        })
        + deploy.spec.template.spec.withVolumes([
            vol.fromPersistentVolumeClaim("chroma-storage-vol", "chroma-storage"),
        ]),

        llms_svc: svcs.serviceFor(self.deployment),
    }

}