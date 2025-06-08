local k = import "k.libsonnet";
local tanka = import 'github.com/grafana/jsonnet-libs/tanka-util/main.libsonnet';
local helm = tanka.helm.new(std.thisFile);

{
  manifest(pim, config):: helm.template("airflow", "../charts/airflow", {
    namespace: pim.namespace,
    values: {
      images: {
        airflow: {
          repository: "andreax79/airflow-code-editor",  // or your custom image
          tag: "2.10.5",
        }
      },
      webserver: {
        env: [
          { name: "AIRFLOW__CODE_EDITOR__ENABLED", value: "true" },
          { name: "AIRFLOW__CODE_EDITOR__GIT_ENABLED", value: "false" },
          { name: "AIRFLOW__CODE_EDITOR__GIT_CMD", value: "/usr/bin/git" },
          { name: "AIRFLOW__CODE_EDITOR__GIT_DEFAULT_ARGS", value: "-c color.ui=true" },
          { name: "AIRFLOW__CODE_EDITOR__GIT_INIT_REPO", value: "false" },
          { name: "AIRFLOW__CODE_EDITOR__ROOT_DIRECTORY", value: "/opt/airflow/dags" },
          { name: "AIRFLOW__CODE_EDITOR__LINE_LENGTH", value: "88" },
          { name: "AIRFLOW__CODE_EDITOR__STRING_NORMALIZATION", value: "false" },
          { name: "AIRFLOW__CODE_EDITOR__MOUNT", value: "name=dags,path=/opt/airflow/dags" },
          { name: "AIRFLOW__CODE_EDITOR__MOUNT1", value: "name=logs,path=/opt/airflow/logs" },
        ],
        extraVolumeMounts: [
          {
            name: "airflow-dags",
            mountPath: "/opt/airflow/dags",
          },
        ],
        extraVolumes: [
          {
            name: "airflow-dags",
            persistentVolumeClaim: {
              claimName: "airflow-dags-pvc",
            },
          },
        ],
      },
      dags: {
        persistence: {
          enabled: true,
          existingClaim: "airflow-dags-pvc",  // Shared RWX PVC
        }
      },
      workers: {
        persistence: {
          size: '2Gi'
        }
      },
      triggerer: {
        persistence: {
          size: '2Gi'
        }
      },
      logs: {
        persistence: {
          size: '2Gi'
        }
      },
    }
  })
}
