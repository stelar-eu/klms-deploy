local kcinit = import "kcinit.libsonnet";

kcinit + {
    env(pim, config): super.env(pim, config) + {
        KC_QUAY_PUSHERS: pim.registry.QUAY_PUSHERS_ROLE,
        KC_QUAY_PULLERS: pim.registry.QUAY_PULLERS_ROLE,
        KC_QUAY_GROUP_CLAIM: pim.registry.KC_ROLES_CLAIM,
    },
}
