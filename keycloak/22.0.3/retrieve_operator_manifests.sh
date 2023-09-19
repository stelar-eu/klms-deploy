#! /bin/bash

# These are the manifests for the keycloak CRDs
kubectl apply -f https://raw.githubusercontent.com/keycloak/keycloak-k8s-resources/22.0.3/kubernetes/keycloaks.k8s.keycloak.org-v1.yml
kubectl apply -f https://raw.githubusercontent.com/keycloak/keycloak-k8s-resources/22.0.3/kubernetes/keycloakrealmimports.k8s.keycloak.org-v1.yml

# Manifest for deploying the operator
kubectl apply -f https://raw.githubusercontent.com/keycloak/keycloak-k8s-resources/22.0.3/kubernetes/kubernetes.yml


# N.B.  Currently the Operator watches only the namespace where the Operator is installed. !!!

