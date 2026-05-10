# lib2

`lib2` is the refactor workspace for the deployment model and Jsonnet layout.

The current shape is:

- one component directory per deployable unit
- one stable `entrypoint.libsonnet` per component
- one local `pim.libsonnet` per component
- one flat `resources/` directory per component
- one shared entrypoint lookup under `lib2/util/`
- a static environment template under `lib2/environment/`

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
  mounts them directly from `manifest(config)`.

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

### Component PSM

Component PSM is environment data for one component, for example:

- secret names
- SMTP settings
- MinIO external URLs
- feature flags

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

`lib2/environment/main.jsonnet` is the target static environment template.

It is intended to be copied into an environment directory and then consume
environment-specific PSM JSON files. In that model:

- the Jsonnet file is static
- only the JSON data changes per environment
- the component names stay in the template
- entrypoint files are resolved through `lib2/util/component_entrypoints.libsonnet`

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

## Notes

- `lib2` is the experimental refactor tree.
- The original `lib/` tree is the restored reference tree.
- Some review templates in `lib2/environment/` are target-shape artifacts and
  are not necessarily the currently active deployment path.
