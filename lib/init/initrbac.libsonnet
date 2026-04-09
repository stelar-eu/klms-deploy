local rbac = import "rbac.libsonnet";

{
    manifest(pim, config): {
        initrbac: rbac.namespacedRBAC("sysinit", [
            rbac.resourceRule(
                ["create", "get", "list", "update", "delete"],
                [""],
                ["secrets", "configmaps"])
        ]),
    }
}
