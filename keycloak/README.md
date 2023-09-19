
# Keycloak notes for STELAR deployment

This directory contains the files needed to deploy the keycloak kubernetes operator, 
and create keycloak realms for STELAR.

## What is the keycloak operator

**NOTE**: The following relate to the new "Quarkus-based" version of keycloak, which as of the
time of this writing, is very recent. 

### What does the operator do

The keycloak operator allows keycloak to be installed in kubernetes in a (semi-) automated
way. The keycloak operator (runs a pod that...) monitors the namespace for new custome resources:

There are two custom resources:
  - keycloaks
  - keycloakrealmimports

**N.B.** Currently the Operator watches only the namespace where the Operator is installed.

### What are these custom resources

A __keycloak__ CR is basically a new installation of keycloak, and requires setting up the system
resources needed:
  - A database (preferably postgresql) for storing the data
  - A DNS name where clients of the keycloak service will communicate
  - Other stuff, e.g., a certificate for above DNS name

The __keycloak__ installation manages a number of __realms__.  Each realm is an independent collection
of settings (users, clients, roles, etc) that a collection of applications can use for authentication, authorization,
SSO etc.

The initial __keycloak__ installation contains a **master** realm. More realms can be created by deploying __keycloakrealmimport__ resources.

## Contens of this directory

The following subdirectories contain the keycloak operator instance.
 22.0.0
 22.0.3

In each there are three .yml files.
Two of the files contain CRDs and the third contains the actual operator deployment.

Current keycloak  version: 22.0.3


