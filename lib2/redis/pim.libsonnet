{
  images: {
    REDIS_IMAGE: 'redis:7',
  },

  ports: {
    REDIS: 6379,
  },

  labels: {
    'app.kubernetes.io/name': 'data-catalog',
    'app.kubernetes.io/component': 'redis',
  },

  probes: {
    liveness: {
      command: ["/usr/local/bin/redis-cli", "-e", "QUIT"],
      initial_delay_seconds: 30,
      period_seconds: 10,
    },
    readiness: {
      command: ["/usr/local/bin/redis-cli", "-e", "QUIT"],
      initial_delay_seconds: 30,
      period_seconds: 10,
    },
  },
}
