from kubernetes import client, config

config.load_incluster_config()
#config.load_kube_config()

v1 = client.CoreV1Api()

#ret = v1.list_pod_for_all_namespaces(watch=False)
ret = v1.list_namespaced_pod(namespace="playground")
for i in ret.items:
    print(f"{i.status.pod_ip}\t{i.metadata.namespace}\t{i.metadata.name}")


batch = client.BatchV1Api()
batch.list_namespaced_job(namespace="playground")
for i in ret.items:
    print(f"{i.status}\t{i.metadata.namespace}\t{i.metadata.name}")


#
# Create a job 
#

container = client.V1Container(
    name="testjob1",
    image="vsam/testservice",
    #command=[]
)

template = client.V1PodTemplateSpec(
    metadata=client.V1ObjectMeta(labels={"app": "pi"}),
    spec=client.V1PodSpec(restart_policy="Never", containers=[container]))
    
# Create the specification of deployment
spec = client.V1JobSpec(
    template=template,
    backoff_limit=4)

# Instantiate the job object
job = client.V1Job(
    api_version="batch/v1",
    kind="Job",
    metadata=client.V1ObjectMeta(name="tool-job"),
    spec=spec)


print("===================================================================")
ret = batch.create_namespaced_job(body=job, namespace="playground")
print(f"Job created. status='{str(ret.status)}'")
print("===================================================================")
print("Created job", ret)

