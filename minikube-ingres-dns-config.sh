#! /bin/bash

# Configure the DNS resolution to use the ingress-dns plugin of minikube.
# This script is suitable for machines where DNS resolution is handled by
# systemd-resolved.service.  Ubuntu after 20.04 should be good.

#set -o xtrace

MINIKUBE_IP=$(minikube ip)
IFACE=$(ip -j route get $MINIKUBE_IP |jq -r .[].dev)


if [ $# -ne 1 ]
  then
    echo 
    echo "No domain supplied. Please provide a domain name as argument."
    echo
    echo "The following is a list of published ingresses and their hosts."
    minikube kubectl -- get ingress -A
else

echo Setting up Domain $1 on minikube ip=$MINIKUBE_IP on iface $IFACE
sudo resolvectl dns $IFACE $MINIKUBE_IP
sudo resolvectl domain $IFACE  '~'"$1"

fi

