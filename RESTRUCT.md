# A new approach to STELAR installation, provisioning and management

The current method of installing the KLMS has reached its limits.  We should move to a new method, that (a) will accomodate Kostas' work on deployment configuration (b) will allow us to install tools, optional components etc in a consistent manner, and (c) will be more amenable to good features: extensibility, documentation, etc.

## Lake installation

The new system will be based on 
  1.  `stelarctl`
  2.  `tanka`
  3.  jsonnet bundler (`jb`)
  4.  `kubectl`


A lake admin would install  stelarctl  (via `pip`),  `tanka` and `jb` (as provided by these tools) and also would initialise a minimal directory structure: let us call it a **workspace**.

```text
+
|  jsonnetfile.json
|- environments
   |- klms1
   |- klms2
|- lib
|- vendor
```

In this scheme, the `lib` directory will actually be empty, reserved for whatever environments the lake admin may decide to have.

The `.libsonnet` files contining the code for STELAR components will actually move under `vendor` and will be downloaded by `jb`  from its github repository (same as with other libraries).

Thus, it will not be necessary for someone to clone the `klms-deploy` repository.

Another benefit is that one can have multiple such workspaces, each version-controlled by git. This allows us to retain the *configuration as code* discipline.

##  Transition towards feature models

The current structure of an installation configuration is quite ad-hoc; difficult to use, complicated to read and has an extremely steep learning curve. 

To get to a more sound place, we should incorporate the concept of Feature Models. In this way, a STELAR installation is part (an
instance of) a  [Software Product Line](https://en.wikipedia.org/wiki/Software_product_line).

[Feature Models](https://en.wikipedia.org/wiki/Feature_model) will allow us to specify all aspects of a STELAR instance in a concise and uniform way. This will replace the current practice of running the *infamous* bootstrap script, and then modifying in an ad-hoc way the jsonnet templates.

This approach will allow us to not only configure a lake core, but also (in the future) to install tools, extensions, and other optional components (e.g., flink/SDE, LLM search engines), in a concise and disciplined manner.

## Issues for discussion

Here are some things to discuss:

### Hide tanka invocation inside stelarctl

Should we hide tanka inside stelarctl?  My opinion is *no, we should not*, although Kostas thought it to be a good idea. My reasoning is that we should trust/require the KLMS admin to understand kubernetes; there are many things that are needed in order to set up a lake, that the STELAR admin
should have full control over, instead of having to fight our tooling.

On the other hand, there are many useful features that our tool can automate *optionally*, ranging from certificate rotation to status monitoring to advanced configuration of the KLMS (that may require interventions both at the cluster level and at the application level). We could very well support these, without locking in our users to an opaque tool.

### Move towards a STELAR operator

Much complex software is installed via an operator, together with some CRDs that describe the installation. I am not sure this is the right way to go with our system; the effort to provide *reconciliation semantics* to the CRDs may be too much. Also, this is again about keeping operations transparent for the admin. 

I do not think that we are near there, but I am keeping an open mind...

