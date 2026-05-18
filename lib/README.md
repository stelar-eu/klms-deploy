# lib

`lib` is the current deployment model and Jsonnet layout.

The current shape is:

- one component directory per deployable unit
- one stable `entrypoint.libsonnet` per component
- one flat `resources/` directory per component
- one shared component registry under `lib/util/`
- a static environment template under `lib/environment/`
- one archive area for legacy files under `lib/unused/`

## Component structure

Each component follows this pattern:

```text
<component>/
  entrypoint.libsonnet
  resources/
    ...
```

### Files

- `entrypoint.libsonnet`
  Stable component entry interface. It imports the component resources and
  mounts them directly from `manifest(psm)`.

- `resources/*.libsonnet`
  Individual Kubernetes resource constructors used by the entrypoint.

## Fullspec Config

The component entrypoints now consume one shared config object derived from the
generated product fullspec. Component-owned values are read from their feature
section, for example `config.api.*` or `config.postgres.*`, while deployment-
wide values live at the root, for example `config.ROOT_DOMAIN`.

## Component entrypoints

Each root component entrypoint imports its resource files directly and mounts
them inside `manifest(config)`.

Example pattern:

```jsonnet
local deployment = import "resources/deployment.libsonnet";
local service = import "resources/service.libsonnet";

{
  manifest(config): {
    deployment: deployment.new(config),
    service: service.new(config),
  },
}
```

## Environment template

`lib/environment/main.jsonnet` is the target static environment template.

It is intended to be copied into an environment directory and then consume a
generated product fullspec JSON file. In that model:

- the Jsonnet file is static
- only the product fullspec JSON changes per environment
- the component names come from `lib/util/components.libsonnet`
- entrypoint files are resolved through `lib/util/components.libsonnet`

## Shared utilities

`lib/util/` holds shared helpers used by the component entrypoints and the
environment template.

Current shared files include:

- `components.libsonnet`
  Static component registry. It exposes:
  - `get(component_name)` to fetch a component entrypoint
  - `get_names()` to fetch the ordered component list

- `transform.libsonnet`
  Legacy composition helper for callers that still want a composition layer.

## System component

`lib/system/` holds deployment-wide resources rather than a product
component. Examples:

- certificates
- RBAC for init jobs
- network policy

These use the same flat pattern as the product components:

```text
lib/system/
  entrypoint.libsonnet
  resources/
    certificates.libsonnet
    initrbac.libsonnet
    network_policy.libsonnet
```

## Unused archive

`lib/unused/` contains legacy Jsonnet files that were moved out of the active
tree because they do not currently have a direct component counterpart.

This directory is not part of the active rendering path.

## Notes

- `lib` is the active refactor tree.
- Some review templates in `lib/environment/` are target-shape artifacts and
  are not necessarily the currently active deployment path.
