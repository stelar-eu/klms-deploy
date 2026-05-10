// Core init RBAC constructor for deployment-wide lib2 resources.
local rbac = import "../../../util/rbac.libsonnet";

{
  new():
    rbac.namespacedRBAC("sysinit", [
      rbac.resourceRule(
        ["create", "get", "list", "update", "delete"],
        [""],
        ["secrets", "configmaps"]
      ),
    ]),
}
