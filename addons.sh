#!bin/bash
echo 'Will enable addons for KLMS deployment'

minikube addons enable csi-hostpath-driver
minikube addons enable metrics-server
minikube addons enable ingress
minikube addons enable ingress-dns
minikube addons enable volumesnapshots

echo 'Minikube addons enabled :)'
