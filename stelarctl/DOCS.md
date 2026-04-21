# stelarctl documentation

`stelarctl` is the operator-facing CLI for deploying and inspecting STELAR
KLMS on Kubernetes. It turns a validated YAML platform model into a Tanka
environment, applies the resulting manifests, records the last successful
desired state, and can infer status from the live cluster.

For implementation-level design notes, see [ARCHITECTURE.txt](ARCHITECTURE.txt).

## Requirements

Before using `stelarctl`, make sure the workstation has:

- Python 3.11 or newer.
- Access to the target cluster through `kubectl`.
- A kubeconfig context whose name matches `k8s_context` in the platform model.
- Grafana Tanka available as `tk`.
- StorageClass and IngressClass objects matching the model.
- A ready cert-manager ClusterIssuer when `infrastructure.tls.mode` is
  `cert-manager`.

The repository wrapper can be used directly:

```bash
./bin/stelarctl --help
```

When installed as a Python package, the console entry point is:

```bash
stelarctl --help
```

## Platform model

The platform model is a YAML file validated by `stelarctl.platform_model`.
Example models live in [example_models](example_models).

Required top-level fields:

| Field | Purpose |
| --- | --- |
| `platform` | Human-readable platform or cluster label. |
| `k8s_context` | Kubernetes context used for deployment and status checks. |
| `namespace` | Namespace that owns the STELAR deployment. |
| `author` | Operator or owner recorded on generated resources. |
| `tier` | Deployment tier: `core` or `full`. |
| `infrastructure` | Storage, ingress, and TLS settings. |
| `dns` | Root domain, URL scheme, and service subdomain prefixes. |
| `config` | Application configuration passed into generated manifests. |
| `secrets` | Secret names and values applied before `tk apply`. |

Minimal shape:

```yaml
platform: "minikube"
k8s_context: "minikube"
namespace: "stelar-lab"
author: "operator@example.org"
tier: "core"

infrastructure:
  storage:
    dynamic_class: "standard"
    provisioning_class: "standard"
  ingress_class: "nginx"
  tls:
    mode: "none"

dns:
  root: "minikube.test"
  scheme: "http"

config:
  smtp_server: "smtp.example.org"
  smtp_port: "587"
  smtp_username: "apikey"
  s3_console_url: "http://klms.minikube.test/s3/login"
  enable_llm_search: false

secrets:
  - name: "postgresdb-secret"
    data: {password: "postgres"}
  - name: "ckandb-secret"
    data: {password: "ckan"}
  - name: "keycloakdb-secret"
    data: {password: "keycloak"}
  - name: "datastoredb-secret"
    data: {password: "datastore"}
  - name: "keycloakroot-secret"
    data: {password: "change-me"}
  - name: "smtpapi-secret"
    data: {password: "smtp-password"}
  - name: "ckanadmin-secret"
    data: {password: "change-me"}
  - name: "minioroot-secret"
    data: {password: "change-me"}
  - name: "session-secret-key"
    data: {key: "change-me"}
  - name: "quaydb-secret"
    data: {password: "quay-password"}
```

Notes:

- `dns.scheme: http` requires `infrastructure.tls.mode: none`.
- `infrastructure.tls.mode: cert-manager` requires `infrastructure.tls.issuer`.
- `config.enable_llm_search: true` also requires `groq_api_url` and
  `groq_api_model`.
- Secret names are part of the model comparison. Secret values can only be
  compared against the stored model, because Kubernetes does not expose
  recoverable plaintext secret values.

## Commands

### Validate a model

Validate YAML and print the selected platform, tier, and namespace:

```bash
./bin/stelarctl validate stelarctl/example_models/minikube.yaml
```

This command does not contact Kubernetes and does not write files.

### Generate a Tanka environment

Materialize `spec.json` and `main.jsonnet` without applying anything:

```bash
./bin/stelarctl generate stelarctl/example_models/minikube.yaml --env environments/minikube.dev
```

Generated files:

- `spec.json`: Tanka environment metadata, context, namespace, and resource
  defaults.
- `main.jsonnet`: Jsonnet entry point generated from the validated model.

### Deploy

Run the full deployment workflow:

```bash
./bin/stelarctl deploy stelarctl/example_models/minikube.yaml --env environments/minikube.dev
```

Deployment flow:

1. Load and validate the input model.
2. Load `<env>/model.yaml` if a previous successful deploy exists.
3. Infer the live STELAR deployment from Kubernetes.
4. Decide whether the input is a no-op, needs a secret confirmation, or needs a
   hard redeploy.
5. Run preflight checks.
6. Write `spec.json` and `main.jsonnet`.
7. Show `tk diff --with-prune`.
8. Ask for confirmation unless `--yes` is supplied.
9. Purge existing deployment resources when a live deployment is active.
10. Annotate the namespace, apply secrets, run `tk apply`, and store the input
    model as `<env>/model.yaml`.

Useful flags:

```bash
./bin/stelarctl deploy model.yaml --env environments/prod --wait
./bin/stelarctl deploy model.yaml --env environments/prod --verify
./bin/stelarctl deploy model.yaml --env environments/prod --yes
./bin/stelarctl deploy model.yaml --env environments/prod --wait-timeout 900 --wait-interval 10
```

`--verify` implies waiting for readiness before service checks run.

### Status

Inspect live deployment progress:

```bash
./bin/stelarctl status --env environments/minikube.dev
```

The target can also be supplied directly:

```bash
./bin/stelarctl status --context minikube --namespace stelar-lab
```

Without `--env`, `--context`, or `--namespace`, `status` uses the active
kubeconfig context and its namespace, defaulting to `default` when no namespace
is configured.

Watch mode refreshes continuously:

```bash
./bin/stelarctl status --env environments/minikube.dev --watch --interval 5
```

Status is inferred from Kubernetes resources, not from `<env>/model.yaml`.
Progress is weighted as 40 percent completed initialization jobs and 60 percent
ready long-running components.

### Secrets

Apply model-defined secrets and generated STELAR secrets:

```bash
./bin/stelarctl secrets-apply model.yaml
```

Skip generated secrets:

```bash
./bin/stelarctl secrets-apply model.yaml --no-generated
```

Delete every secret in the model namespace:

```bash
./bin/stelarctl secrets-delete model.yaml
./bin/stelarctl secrets-delete model.yaml --yes
```

`secrets-delete` is namespace-wide. Use it only when that namespace is dedicated
to the target STELAR deployment.

### Teardown

Purge deployment resources while keeping the namespace and local environment:

```bash
./bin/stelarctl teardown --env environments/minikube.dev
```

Target a cluster and namespace directly:

```bash
./bin/stelarctl teardown --context minikube --namespace stelar-lab
```

Optional cleanup:

```bash
./bin/stelarctl teardown --env environments/minikube.dev --delete-namespace --delete-env
```

`--delete-env` requires `--env`.

## Deployment state model

`stelarctl deploy` compares three possible views of state:

- Input model: the YAML file passed to `deploy`.
- Stored model: `<env>/model.yaml`, written after a successful deploy.
- Inferred live model: reconstructed from Kubernetes resources.

The stored model is preferred when it agrees with the live cluster because it
preserves secret values. If the stored model is missing or appears stale,
`stelarctl` falls back to the inferred live model and prompts when secret values
are the only unverifiable part of the comparison.

Current deployments use a hard-redeploy strategy for meaningful changes. A hard
redeploy purges known STELAR resources in the namespace before applying the new
Tanka output.

## Generated and managed files

Inside the Tanka environment directory, `stelarctl` manages:

- `spec.json`
- `main.jsonnet`
- `model.yaml`

Avoid manually editing these files for long-lived changes. Edit the platform
model instead, then run `generate` or `deploy`.

## Troubleshooting

Common failure points:

- `Kubernetes context '<name>' not found`: update kubeconfig or fix
  `k8s_context`.
- `StorageClass '<name>' ... does not exist`: create the class or update
  `infrastructure.storage`.
- `IngressClass '<name>' ... does not exist`: create the class or update
  `infrastructure.ingress_class`.
- `ClusterIssuer '<name>' ... does not exist` or is not Ready: fix cert-manager
  before deploying with `tls.mode: cert-manager`.
- `Timed out waiting ... Ready 100%`: run `status --watch` and inspect blockers.
- `Degraded`: at least one expected job failed or a pod is waiting in a known
  failure state such as `CrashLoopBackOff` or `ImagePullBackOff`.
