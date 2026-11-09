# STELAR Jsonnet deployment library

`lib/` is the active Jsonnet/Tanka library rendered by STELAR lake workspaces.
It is not a standalone workspace and contains no cluster-specific environment.
`stelarctl workspace init` writes a dependency manifest that points Jsonnet
Bundler at this subdirectory; `jb install` then installs it as `vendor/lib/` in
the operator's workspace.

## Public entrypoints

- `environment_templates/main_template.jsonnet` is copied by `stelarctl lake
  add` into each managed environment as `main.jsonnet`.
- `util/build_lake.libsonnet` reads `spec.stelar.active_product`, derives the
  selected components and shared configuration, and renders their manifests.
- `util/components.libsonnet` maps feature-model component names to stable
  component entrypoints.

These files form the integration contract between `stelarctl` and the Tanka
library. Changes to their paths or inputs must remain synchronized with the
packaged workspace template and the CLI tests.

## Component layout

Each deployable component has a stable entrypoint and resource constructors:

```text
<component>/
  entrypoint.libsonnet
  resources/
    deployment.libsonnet
    service.libsonnet
    ...
```

An entrypoint exposes `manifest(config)` and returns the Kubernetes resources
for that component. Resource constructors use the shared fullspec-derived
configuration. Component values live under sections such as `config.api` or
`config.postgres`; deployment-wide values such as `ROOT_DOMAIN` live at the
configuration root.

## Shared code

- `util/` contains Kubernetes constructors, component selection, fullspec
  transformation, ingress helpers, storage helpers, and the `k.libsonnet`
  alias for the installed Kubernetes Jsonnet library.
- `system/` renders deployment-wide resources such as network policy,
  certificates, and init-job RBAC.
- `environment_templates/` contains only the static managed environment
  entrypoint copied into operator workspaces.

No generated product, Kubernetes target, credentials, or Tanka `spec.json`
belongs in this directory.

## Tests

The Python-based Jsonnet tests live under `tests/jsonnet_lib/`. Their dependency
manifest is deliberately kept with the tests rather than at the repository
root, so this source repository cannot be mistaken for an operator workspace.
