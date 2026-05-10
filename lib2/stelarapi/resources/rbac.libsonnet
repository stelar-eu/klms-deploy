// Core RBAC constructor for the stelarapi component.
local rbac = import "../../util/rbac.libsonnet";

{
  new(_config):
    rbac.namespacedRBAC("stelarapi", [
      rbac.resourceRule(
        ["get", "list", "watch"],
        [""],
        ["*"]
      ),
      rbac.resourceRule(
        ["create", "delete", "deletecollection", "get", "list", "patch", "update", "watch"],
        ["batch"],
        ["jobs"]
      ),
    ])
}
