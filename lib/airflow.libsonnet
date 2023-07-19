/*
    Logic for configuring Apache airflow.

    The basis for airflow is the official helm chart, which must be
    installed in path ./charts/airflow.

    The following command can be used to vendor charts
    $ tk tool charts add <repo>/<name>@<version>

    We have used the following commands:

    tk tool charts add-repo apache_airflow https://airflow.apache.org
    tk tool charts add apache_airflow/airflow@1.9.0

 */

local k = import "k.libsonnet";
local tanka = import 'github.com/grafana/jsonnet-libs/tanka-util/main.libsonnet';
local helm = tanka.helm.new(std.thisFile);
# local kustomize = tanka.kustomize.new(std.thisFile);

{
    local deployment = k.apps.v1.deployment,
    local container = k.core.v1.container,
    local pod = k.core.v1.pod,
    local port = k.core.v1.containerPort,
    local volumeMount = k.core.v1.volumeMount,
    local volume = k.core.v1.volume,
    local service = k.core.v1.service,

    // The path to the vendored airflow chart must be relative...
    new(namespace): helm.template("airflow", "../charts/airflow", {
        namespace: namespace,
        webserverSecretKey: '6d2ee82cc7dc510dd99fcec80fce4958',
        values: {
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
        },
    })
}
