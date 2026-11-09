# STELAR KLMS deployment tooling

This repository publishes two things used to deploy the STELAR Knowledge Lake
Management System (KLMS):

- `stelarctl`, the operator CLI distributed as the `stelar-deploy` Python
  package;
- `lib/`, the Jsonnet/Tanka deployment library downloaded into an operator's
  workspace by Jsonnet Bundler.

The repository itself is source code, not a deployable Tanka workspace. Do not
clone it to create a lake. Install `stelarctl`, initialize a separate workspace,
and let `jb install` download the deployment library and its dependencies.

## Install

Install the CLI with `pipx`:

```bash
pipx install stelar-deploy
stelarctl --help
```

The operator machine also needs Tanka (`tk`), Jsonnet Bundler (`jb`), Jsonnet,
and `kubectl`. Keep `kubectl` configured with the context that will host the
lake.

## Deployment lifecycle

Create and enter a workspace outside this source checkout:

```bash
stelarctl workspace init ./lake-workspace
cd ./lake-workspace
jb install
```

Create an environment and product, validate the target cluster, bootstrap the
non-rendered resources, and then apply the Tanka environment:

```bash
stelarctl lake add dev --infer
stelarctl lake create --minimal minimal dev
stelarctl lake verify dev
stelarctl lake bootstrap dev --export-credentials ./dev-credentials.txt
tk apply dev
stelarctl lake status dev
```

`lake add --infer` records the active kubeconfig context and its configured
namespace. Either value can instead be supplied explicitly with `--context` or
`--namespace`; `--infer` fills only a missing value.

The credentials export is optional, contains plaintext secrets, and is created
with mode `0600` on POSIX systems. Store it securely and delete it when it is no
longer needed.

Cleanup has two explicit phases:

```bash
tk delete dev
stelarctl lake unbootstrap dev
```

`tk delete` removes rendered Kubernetes workloads. `lake unbootstrap` removes
the bootstrap and init-generated Secrets and ConfigMaps selected by the lake
fullspec.

## Repository layout

- `src/stelar/deploy/` — CLI, feature model, operations, and packaged workspace
  templates.
- `lib/` — active Jsonnet/Tanka deployment library consumed through `jb`.
- `tests/stelarctl/` — CLI and operation tests.
- `tests/jsonnet_lib/` — Jsonnet library tests and their development-only
  dependency manifest.
- `docs/stelarctl.md` — current command and lifecycle reference.

The dependency manifest written by `stelarctl workspace init` is
`src/stelar/deploy/templates/jsonnetfile.json`. It downloads the `lib`
subdirectory of this repository plus the required external Jsonnet libraries.
The source repository deliberately has no root `jsonnetfile.json`, `spec.json`,
or committed Tanka environment.

## Documentation

- [stelarctl command reference](docs/stelarctl.md)
- [Failure and safety behavior](docs/stelarctl_failure_cases.md)
- [Jsonnet library structure](lib/README.md)
- [Feature model diagram](artifacts/feature-model/stelar-feature-model.svg)

## Development

Install the package and test dependencies in a virtual environment, then run:

```bash
python -m pytest tests/stelarctl
```

Jsonnet library tests need their external dependencies in the ignored root
`vendor/` directory. See
[tests/jsonnet_lib/README.md](tests/jsonnet_lib/README.md) for the isolated
development setup.

## License

This project is licensed under the [GPL-2.0 license](LICENSE).
