local k = import "k.libsonnet";

local ENV = {
    MINIO_ROOT_USER : "root",
    MINIO_ROOT_PASSWORD: 'stelartuc',
    MINIO_BROWSER_REDIRECT: 'true',
    MINIO_BROWSER_REDIRECT_URL: 'https://tb.petrounetwork.gr/s3',
};

{   
    ENV: ENV,
}