# Notes on deploying and configuring MINIO tenants for STELAR

MINIO tenants on kubernetes can be deployed after installing the minio operator.

A MINIO tenant provides two services, 
  1. one named "<tenant>-console" (of course <tenant> represents the tenant name), 
  2. One named "minio" which provides the S3 API to the data.

To be accessible from outside the cluster, both of these need to be exposed by ingress.
They can both be exposed to the same DNS name, and a TLS certificate will be 
useful in securing HTTPS access.

