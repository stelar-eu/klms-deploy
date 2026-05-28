// Core Deployment constructor for the llm_search component.
local images = import "../../util/imgutil.libsonnet";
local k = import "../../util/k.libsonnet";

local deploy = k.apps.v1.deployment;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;
local envSource = k.core.v1.envVarSource;
local volumeMount = k.core.v1.volumeMount;
local vol = k.core.v1.volume;

{
  new(config):
    local image = images.image_name(config.llm_search.IMAGE);
    local pull_policy = images.pull_policy(config.llm_search.IMAGE);
    deploy.new(
      name = "llmsearch",
      containers = [
        container.new("llmsearch", image)
        + container.withImagePullPolicy(pull_policy)
        + container.withEnvMap({
          GROQ_URL: config.llm_search.GROQ_API_URL,
          GROQ_MODEL: config.llm_search.GROQ_MODEL,
          LLM_OPTION: config.llm_search.LLM_OPTION,
          CHROMA_DIR: config.llm_search.CHROMA_DIR,
          REDIS_URL: "redis://redis:" + std.toString(config.redis.PORT) + "/5",
        })
        + container.withEnvMap({
          GROQ_API_KEY: envSource.secretKeyRef.withName(config.llm_search.GROQ_API_KEY_SECRET_NAME) + envSource.secretKeyRef.withKey("key"),
        })
        + container.withPorts([
          containerPort.newNamed(config.llm_search.PORT, "api"),
        ])
        + container.withVolumeMounts([
          volumeMount.new("chroma-storage-vol", config.llm_search.CHROMA_DIR, false),
        ]),
      ],
      podLabels = {
        "app.kubernetes.io/name": "llmsearch",
        "app.kubernetes.io/component": "llmsearch",
      }
    )
    + deploy.spec.template.spec.withVolumes([
      vol.fromPersistentVolumeClaim("chroma-storage-vol", "chroma-storage"),
    ])
}
