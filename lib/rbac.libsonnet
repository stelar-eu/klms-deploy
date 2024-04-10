/*
    Utilities to quickly create RBAC objects.

 
    clusterRBAC(name, rules, namespace) 
      creates a ServiceAccount, ClusterRole and ClusterRoleBinding with the given
      name and rules.

    namespacedRBAC(name, rules, namespace) 
      creates a ServiceAccount, Role and RoleBinding with the given name and rules.

    - 'name' is used for all three objects
    - 'rules' is a list of policyRule objects
    - 'namespace' is used for the ServiceAccount, Role and RoleBinding


    resourceRule(verbs, apiGroups, resources)


 */

local k = import "k.libsonnet";

/* K8S API MODEL */
local deploy = k.apps.v1.deployment;
local stateful = k.apps.v1.statefulSet;
local container = k.core.v1.container;
local containerPort = k.core.v1.containerPort;
local servicePort = k.core.v1.servicePort;
local volumeMount = k.core.v1.volumeMount;
local pod = k.core.v1.pod;
local vol = k.core.v1.volume;
local service = k.core.v1.service;
local cm = k.core.v1.configMap;
local secret = k.core.v1.secret;

local role = k.rbac.v1.role;
local roleBinding = k.rbac.v1.roleBinding;
local clusterRole = k.rbac.v1.clusterRole;
local clusterRoleBinding = k.rbac.v1.clusterRoleBinding;
local subject = k.rbac.v1.subject;
local serviceAccount = k.core.v1.serviceAccount;
local policyRule = k.rbac.v1.policyRule;



local opt_object(func, val)=
    if std.type(val)=="null" then {} else func(val);


{
  clusterRBAC(name, rules, namespace):: {

    service_account:
      serviceAccount.new(name),

    cluster_role:
      clusterRole.new(name) +
      clusterRole.withRules(rules),

    cluster_role_binding:
      clusterRoleBinding.new(name) +
      clusterRoleBinding.mixin.roleRef.withApiGroup('rbac.authorization.k8s.io') +
      clusterRoleBinding.mixin.roleRef.withKind('ClusterRole') +
      clusterRoleBinding.mixin.roleRef.withName(name) +
      clusterRoleBinding.withSubjects([
        subject.withKind('ServiceAccount') +
        subject.withName(name) +
        subject.withNamespace(namespace),
      ]),
  },


  // namespaceRBAC creates a service account, 
  // Role and RoleBinding with the given
  // name and rules.
  namespacedRBAC(name, rules, namespace=null):: {

    service_account:
      serviceAccount.new(name) +
      serviceAccount.mixin.metadata.withNamespace(namespace),

    role:
      role.new(name) +
      role.mixin.metadata.withNamespace(namespace) +
      role.withRules(rules),

    role_binding:
      roleBinding.new(name) +
      roleBinding.mixin.metadata.withNamespace(namespace) +
      roleBinding.mixin.roleRef.withApiGroup('rbac.authorization.k8s.io') +
      roleBinding.mixin.roleRef.withKind('Role') +
      roleBinding.mixin.roleRef.withName(name) +
      roleBinding.withSubjects([
        subject.withKind('ServiceAccount') +
        subject.withName(name) +
        subject.withNamespace(namespace),
      ]),
  },


  resourceRule(verbs, apiGroups, resources)::
    policyRule.withVerbs(verbs) +
    policyRule.withApiGroups(apiGroups) +
    policyRule.withResources(resources)
    ,


}