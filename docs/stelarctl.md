# stelarctl

`stelarctl` is the deployment helper for preparing a KLMS lake workspace before
the rendered manifests are applied with Tanka.

It keeps three responsibilities separate:

- workspace and environment scaffolding
- product specification expansion into `product_fullspec.json`
- cluster preflight checks and bootstrap secrets

## Installation

The intended installation path for operators is `pipx`:

```bash
pipx install stelar-deploy
stelarctl --help
```

`pipx` creates an isolated Python environment for the package and exposes the
`stelarctl` command on the user's PATH. This is not a standalone binary; it is a
Python console script installed in an isolated environment.

For local development from this repository:

```bash
pipx install .
stelarctl --help
```

## Deployment workflow

Run these commands from any directory, using `--workspace` when the workspace is
not the current directory.

```bash
stelarctl init-lake workspace ./lake-workspace
cd ./lake-workspace
jb install
stelarctl init-lake environment linode --workspace .
stelarctl generate-lakespec product.yaml linode --workspace .
stelarctl init-lake cluster linode --workspace . --context my-kube-context
tk apply environments/linode
```

The environment argument accepts either `linode` or `environments/linode`.

## Commands

### init-lake workspace

```bash
stelarctl init-lake workspace WORKSPACE [--force]
```

Creates the workspace directory, creates `lib/`, and writes
`jsonnetfile.json`.

If `jsonnetfile.json` already exists, the command checks for the required lake
Jsonnet dependencies and adds only the missing ones. Existing dependency pins
are preserved when the dependency source is already present.

Use `--force` to rewrite `jsonnetfile.json` from the packaged template.

After this command, run `jb install` from the workspace root so the deployment
library and Jsonnet dependencies are available under `vendor/`.

### init-lake environment

```bash
stelarctl init-lake environment ENV --workspace WORKSPACE
```

Creates `environments/ENV`, copies `main.jsonnet` from the vendored STELAR
deployment library, and creates a minimal `spec.json` skeleton.

This command expects `jb install` to have already populated:

```text
vendor/github.com/stelar-eu/klms-deploy/lib/environment_templates/main.jsonnet
```

Existing `main.jsonnet` and `spec.json` files are not overwritten.

### generate-lakespec

```bash
stelarctl generate-lakespec PRODUCT ENV --workspace WORKSPACE
```

Loads a product JSON or YAML file, validates it against the feature model, and
writes both generated files into the environment:

```text
environments/ENV/product.json
environments/ENV/product_fullspec.json
```

The fullspec is also printed to stdout for inspection.

### init-lake cluster

```bash
stelarctl init-lake cluster ENV --workspace WORKSPACE [--context CONTEXT]
```

Populates the environment `spec.json` with the Kubernetes context, namespace,
and Tanka metadata, then runs cluster preflight checks and creates missing
bootstrap secrets.

The current checks are:

- workspace and environment files exist
- Kubernetes context exists and can be loaded
- configured namespace exists
- configured dynamic storage class exists
- configured provisioning storage class exists
- `nginx` IngressClass exists
- a ready ingress-nginx controller pod exists
- for HTTPS deployments, cert-manager CRDs and deployments exist
- for HTTPS deployments, the configured ClusterIssuer exists and is Ready

Secrets are created only when missing. Existing secrets are left untouched.

## Idempotency

The `init-lake` commands are intended to be rerunnable:

- `workspace` reuses directories and merges missing Jsonnet dependencies
- `environment` reuses directories and does not overwrite existing files
- `cluster` updates `spec.json`, validates the cluster, and skips existing
  secrets

The only destructive option is `init-lake workspace --force`, which rewrites
`jsonnetfile.json`.

## Code layout

The CLI is split so future commands can be added without expanding the
entrypoint module:

- `src/stelar/deploy/cli.py`: stable console-script entrypoint
- `src/stelar/deploy/cli_app.py`: Typer app construction
- `src/stelar/deploy/cli_commands/`: CLI adapters and command registration
- `src/stelar/deploy/commands/`: command business logic
- `src/stelar/deploy/commands/progress.py`: no-op progress interfaces
- `src/stelar/deploy/cli_progress.py`: Typer progress output
- `src/stelar/deploy/templates/jsonnetfile.json`: packaged workspace template

Business logic should not print directly. Add user-facing output through a CLI
adapter or progress reporter so the behavior remains testable without a CLI
runner.

To add a future command group:

1. Add testable business logic under `src/stelar/deploy/commands/`.
2. Add a Typer adapter under `src/stelar/deploy/cli_commands/`.
3. Register the adapter in `src/stelar/deploy/cli_commands/__init__.py`.
4. Keep Kubernetes, Tanka, and filesystem behavior outside the CLI adapter when
   possible.
5. Add unit tests for business behavior and focused CLI tests for argument and
   progress output.
