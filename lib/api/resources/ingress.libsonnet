// Core Ingress constructor for the stelarapi component.
local stelar_ingress = import "../../util/stelar_ingress.libsonnet";

{
  new(config):
    stelar_ingress.new(
      "stelar",
      {
        "nginx.ingress.kubernetes.io/proxy-body-size": "5120m",
        "nginx.ingress.kubernetes.io/x-forwarded-prefix": "/$1",
        "nginx.ingress.kubernetes.io/rewrite-target": "/$3",
        "nginx.ingress.kubernetes.io/app-root": "/stelar",
        "nginx.ingress.kubernetes.io/configuration-snippet": |||
          if ($uri = "/s3") {
            return 308 /s3/;
          }
        |||,
      },
      config.PRIMARY_SUBDOMAIN,
      [
        ["/", "Exact", "stelarapi", "apiserver-api"],
        ["/(dc)(/|$)(.*)", "ImplementationSpecific", "ckan", "api"],
        ["/(stelar)(/|$)(.*)", "ImplementationSpecific", "stelarapi", "apiserver-api"],
        ["/(s3)(/|$)(.*)", "ImplementationSpecific", "minio", "minio-minio"],
        ["/(kg)(/|$)(.*)", "ImplementationSpecific", "ontop", "ontop-ontop"],
        ["/(visualizer)(/|$)(.*)", "ImplementationSpecific", "visualizer", "profvis-vis"],
        ["/(previewer)(/|$)(.*)", "ImplementationSpecific", "previewer", "resprev-ui"],
        ["/(sde)(/|$)(.*)", "ImplementationSpecific", "sde-manager", "sdeui-sdeui"],
        ["/(airflow)(/|$)(.*)", "ImplementationSpecific", "airflow-webserver", "airflow-ui"],
        //["/(kafka)(/|$)(.*)", "ImplementationSpecific", "kafbat", "kafbat-kfb"],
        //["/(flink)(/|$)(.*)", "ImplementationSpecific", "flink-cluster", "jmanager-fl"]
      ],
      config
    )
}
