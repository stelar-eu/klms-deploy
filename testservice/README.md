= How to create images for kubernetes

Just create an image for docker, build it and push it to a public repo.
```
docker build . -t vsam/testservice
docker push vsam/testservice
```

Above, we assume that we have an account to docker hub. If not, you need to
either create one or somehow push the image to an accesible docker image registry.

Then, you can create pod (or other Kubernetes variant for execution) using this image.

For example, 
```
kubectl create job testserv1 --image=vsam/testservice
kubectl get jobs.batch -o wide
kubectl logs jobs/testserv1 
```
