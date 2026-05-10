// Static local model for the minio component.
{
  images: {
    MINIO_IMAGE: 'quay.io/minio/minio:RELEASE.2025-04-22T22-12-26Z-cpuv1',
  },

  labels: {
    'app.kubernetes.io/name': 'object-storage',
    'app.kubernetes.io/component': 'minio',
  },

  ports: {
    MINIO: 9001,
    MINIOAPI: 9000,
  },

  pvc: {
    name: 'minio-storage',
    size: '2Gi',
    volume_name: 'minio-storage-vol',
    mount_path: '/data',
  },

  minio: {
    MINIO_BROWSER_REDIRECT: 'true',
  },

  deployment: {
    image_pull_policy: 'Always',
  },
}
