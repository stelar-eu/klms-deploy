#! /bin/bash

# Create a minikube profile for the debug version of stelar

minikube start --driver=docker --cpus=no-limit --memory=no-limit --insecure-registry "10.0.0.0/24"

