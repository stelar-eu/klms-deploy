# stelarctl Behavior Review

Current model: local files describe desired render state; the cluster records
bootstrap state.

- `lake add` creates or marks a local Tanka environment.
- `lake create` writes named product and fullspec files.
- The first product is selected automatically in `spec.stelar.active_product`.
- `lake switch PRODUCT ENV` changes that local render selection.
- `lake bootstrap` creates Secrets and then writes ConfigMap `stelar-lake-state` in the target namespace.
- `lake status` reads `stelar-lake-state` and reports cluster state from the fullspec stored there.
- `lake unbootstrap` deletes Secrets derived from the ConfigMap fullspec, then deletes `stelar-lake-state`.

`spec.stelar.bootstrapped_product` is legacy local state only. New bootstrap
state is not recorded in `spec.json`.
