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
