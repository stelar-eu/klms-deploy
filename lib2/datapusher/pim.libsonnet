// Static local model for the datapusher component.
{
  images: {
    DATAPUSHER_IMAGE: 'ckan/ckan-base-datapusher:0.0.20',
  },

  ports: {
    DATAPUSHER: 8800,
  },

  labels: {
    'app.kubernetes.io/name': 'data-catalog',
    'app.kubernetes.io/component': 'datapusher',
  },

  probes: {
    liveness: {
      command: ["/usr/bin/wget", "-qO", "/dev/null", "http://127.0.0.1:8800"],
      initial_delay_seconds: 30,
      period_seconds: 15,
      timeout_seconds: 10,
      failure_threshold: 5,
    },
    readiness: {
      port: 8800,
      initial_delay_seconds: 15,
      period_seconds: 15,
      timeout_seconds: 10,
      failure_threshold: 5,
      success_threshold: 1,
    },
  },
}
