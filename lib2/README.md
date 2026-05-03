# lib2

`lib2` is the refactor workspace for the deployment model and Jsonnet layout.

The goal is to move away from one broad shared `pim`/`configuration` object and
toward:

- local component PIMs
- per-environment PSM JSON data
- tier-based composition
- a static environment `main.jsonnet`

## Current structure

Each component lives under its own top-level directory:

```text
lib2/
  ckan/
  datapusher/
  db/
  keycloak/
  minio/
  ontop/
  redis/
  registry/
  solr/
  stelarapi/
  system/
```

Each component follows this pattern:

```text
<component>/
  entrypoint.libsonnet
  pim.libsonnet
  resources/
    core/
      tier.libsonnet
      ...
    full/
      tier.libsonnet
```

### Files

- `entrypoint.libsonnet`
  Stable component entry interface.

- `pim.libsonnet`
  Static component-owned model data.

- `resources/<tier>/tier.libsonnet`
  Tier-specific composition for that component.

- `resources/<tier>/*.libsonnet`
  Individual Kubernetes resource constructors.

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

- `tier`
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

## Tier selection inside components

Each root component entrypoint imports its available tier implementations and
delegates tier selection to `lib2/util/tier_selector.libsonnet`.

Current pattern:

```jsonnet
local tier_selector = import "../util/tier_selector.libsonnet";
local core = import "resources/core/tier.libsonnet";
local full = import "resources/full/tier.libsonnet";

local tiers = {
  core: core,
  full: full,
};

{
  manifest(config): tier_selector.render_selected_tier(config, tiers),
}
```

This keeps:

- one stable entrypoint per component
- one tier registry per component
- one shared tier-selection helper

## Tier metadata for environments

Static tier membership lives under:

```text
lib2/tiers/
  core/
    component_names.libsonnet
    entrypoints.libsonnet
  full/
    component_names.libsonnet
    entrypoints.libsonnet
```

Current use:

- `component_names.libsonnet`
  Review/template path for driving a loop from component metadata.

- `entrypoints.libsonnet`
  Static imported entrypoint list for the current environment path.

`lib2/util/tier_components.libsonnet` selects the tier list to use.

## Environment template

`lib2/environment/main.jsonnet` is the target static environment template.

It is intended to be copied into an environment directory and then consume
environment-specific PSM JSON files. In that model:

- the Jsonnet file is static
- only the JSON data changes per environment

The current review template assumes:

```text
psm/cluster.json
psm/components/index.json
```

relative to the copied environment file.

## System component

`lib2/system/` holds deployment-wide resources rather than a product
component. Examples:

- certificates
- RBAC for init jobs
- network policy

These are still tiered through:

```text
lib2/system/resources/core/tier.libsonnet
lib2/system/resources/full/tier.libsonnet
```

## Notes

- `lib2` is the experimental refactor tree.
- The original `lib/` tree is the restored reference tree.
- Some review templates in `lib2/environment/` are target-shape artifacts and
  are not necessarily the currently active deployment path.
