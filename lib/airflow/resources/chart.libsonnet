// Helm-backed manifest constructor for the airflow component.
local tanka = import "github.com/grafana/jsonnet-libs/tanka-util/main.libsonnet";
local helm = tanka.helm.new(std.thisFile);

local env_list(config) = [
  { name: name, value: config.env[name] }
  for name in std.objectFields(config.env)
];

{
  new(config):
    helm.template(config.release.name, config.release.chart_path, {
      namespace: config.namespace,
      values: {
        images: config.images,
        webserver: {
          env: env_list(config),
          extraVolumeMounts: [
            {
              name: config.webserver.dags_volume_name,
              mountPath: config.webserver.dags_mount_path,
            },
          ],
          extraVolumes: [
            {
              name: config.webserver.dags_volume_name,
              persistentVolumeClaim: {
                claimName: config.webserver.dags_existing_claim,
              },
            },
          ],
        },
        dags: {
          persistence: {
            enabled: true,
            existingClaim: config.webserver.dags_existing_claim,
          },
        },
        workers: {
          persistence: {
            size: config.persistence.workers_size,
          },
        },
        triggerer: {
          persistence: {
            size: config.persistence.triggerer_size,
          },
        },
        logs: {
          persistence: {
            size: config.persistence.logs_size,
          },
        },
      },
    }),
}
