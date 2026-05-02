local rbac = import "../../../util/rbac.libsonnet";

{
  new():
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
    ]),
}
