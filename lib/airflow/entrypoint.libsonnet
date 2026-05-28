// Stable root entrypoint for the airflow component.
local airflow_chart = import "resources/chart.libsonnet";

{
  manifest(config): {
    chart: airflow_chart.new(config),
  },
}
