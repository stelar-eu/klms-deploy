= Installing APISIX for testing

Installed APISIX by
```
% helm repo add apisix https://charts.apiseven.com

% helm repo update

% helm search repo apisix
NAME                            	CHART VERSION	APP VERSION	DESCRIPTION                                       
apisix/apisix                   	2.2.0        	3.5.0      	A Helm chart for Apache APISIX v3                 
apisix/apisix-dashboard         	0.8.1        	3.0.0      	A Helm chart for Apache APISIX Dashboard          
apisix/apisix-ingress-controller	0.12.1       	1.7.0      	Apache APISIX Ingress Controller for Kubernetes   
bitnami/apisix                  	2.1.3        	3.5.0      	Apache APISIX is high-performance, real-time AP...

% helm upgrade --install apisix apisix/apisix --create-namespace --namespace apisix --set dashboard.enabled=true --set ingress-controller.enabled=true --set ingress-controller.config.apisix.serviceNamespace=apisix

```

then, created an ingress.

```
kubectl create ingress a7gw-ingress --rule="stelar.vsamtuc.top/*=apisix-gateway:80" --class=nginx --save-config=true --namespace=apisix
```
