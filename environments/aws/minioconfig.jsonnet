local k = import "k.libsonnet";

local ENV = {
    MINIO_ROOT_USER : "root",
    MINIO_ROOT_PASSWORD: 'stelartuc',
    MINIO_BROWSER_REDIRECT: 'true',
    MINIO_BROWSER_REDIRECT_URL: 'https://klms.stelar.gr/s3',
    MINIO_IDENTITY_OPENID_REDIRECT_URI: 'https://klms.stelar.gr/s3',
};

{   
    ENV: ENV,
}