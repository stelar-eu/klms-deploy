# lib2

`lib2` is the refactor workspace for the deployment model and Jsonnet layout.

The current shape is:

- one component directory per deployable unit
- one stable `entrypoint.libsonnet` per component
- one local `pim.libsonnet` per component
- one flat `resources/` directory per component
- one shared component registry under `lib2/util/`
- a static environment template under `lib2/environment/`
- one archive area for legacy files under `lib2/unused/`

## Component structure

Each component follows this pattern:

```text
<component>/
  entrypoint.libsonnet
  pim.libsonnet
  resources/
    ...
```

### Files

- `entrypoint.libsonnet`
  Stable component entry interface. It imports the component resources and
  mounts them directly from `manifest(psm)`.

- `pim.libsonnet`
  Static component-owned model data.

- `resources/*.libsonnet`
  Individual Kubernetes resource constructors used by the entrypoint.

## PIM vs PSM

### Local PIM

A local component `pim.libsonnet` contains static values owned by that
component, for example:

- image reference
- labels
- service names
- probe defaults
- mount paths
- static env defaults

### Cluster PSM

Cluster PSM is environment data, not code. It should contain deployment-wide
dynamic values such as:

- `namespace`
- `dynamic_volume_storage_class`
- ingress/domain information
- issuer information

At render time it is merged with the component PSM before calling the
component entrypoint.

### Component PSM

Component PSM is environment data for one component, for example:

- secret names
- SMTP settings
- MinIO external URLs
- feature flags

At render time it is merged with the cluster PSM and passed as the single
`psm` argument to `manifest(psm)`.

## Component entrypoints

Each root component entrypoint imports its resource files directly and mounts
them inside `manifest(psm)`.

Example pattern:

```jsonnet
local deployment = import "resources/deployment.libsonnet";
local service = import "resources/service.libsonnet";

{
  manifest(psm): {
    deployment: deployment.new(psm),
    service: service.new(psm),
  },
}
```

## Environment template

`lib2/environment/main.jsonnet` is the target static environment template.

It is intended to be copied into an environment directory and then consume
environment-specific PSM JSON files. In that model:

- the Jsonnet file is static
- only the JSON data changes per environment
- the component names come from `lib2/util/components.libsonnet`
- entrypoint files are resolved through `lib2/util/components.libsonnet`

## Shared utilities

`lib2/util/` holds shared helpers used by the component entrypoints and the
environment template.

Current shared files include:

- `components.libsonnet`
  Static component registry. It exposes:
  - `get(component_name)` to fetch a component entrypoint
  - `get_names()` to fetch the ordered component list

- `transform.libsonnet`
  Legacy composition helper for callers that still want to render from a
  `cluster_psm`, a component-PSM map, and a component registry.

## System component

`lib2/system/` holds deployment-wide resources rather than a product
component. Examples:

- certificates
- RBAC for init jobs
- network policy

These use the same flat pattern as the product components:

```text
lib2/system/
  entrypoint.libsonnet
  pim.libsonnet
  resources/
    certificates.libsonnet
    initrbac.libsonnet
    network_policy.libsonnet
```

## Unused archive

`lib2/unused/` contains legacy Jsonnet files that were moved out of the active
`lib/` tree because they do not currently have a direct `lib2` counterpart.

This directory is not part of the active `lib2` rendering path.

## Notes

- `lib2` is the experimental refactor tree.
- The original `lib/` tree is the restored reference tree.
- Some review templates in `lib2/environment/` are target-shape artifacts and
  are not necessarily the currently active deployment path.
