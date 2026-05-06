#
# Products are tree-like structures that represent the selected and configured features for a deployment. They are generated from the feature model and the selected features, and they are used to generate the deployment configuration.
# A product is a member of a product line defined by a feature model.
#

from copy import deepcopy
from typing import Any
from collections import defaultdict

from pydantic import BaseModel, JsonValue, BaseModel, Field, model_validator

from .feature import (
    Feature,
    FeatureModel,
    SubfeatureGroup,
    JsonSchemaValidator,
)

JsonObject = dict[str, Any]


class Product(BaseModel):
    """A product is a tree-like structure that represents the selected and
    configured features for a deployment."""

    # apiVersion: str = Field(..., description="The API version of this product.")
    # kind: str = Field(..., description="The kind of this product.")

    # Todo: the feature model for this product should probably be specified in the spec.

    # Below are attributes from the legacy bootstrap spec.
    #
    # k8s_context: str = Field(..., description="The Kubernetes context for this product.")
    # namespace: str = Field(..., description="The Kubernetes namespace for this product.")
    # author: str = Field(..., description="The author of this product.")
    # platform: str = Field(..., description="The target platform for this product.")
    # env_name: str = Field(..., description="The name of the environment for this product.")

    # The root feature of the product, which is the same as the root feature of the feature model.
    spec: JsonObject = Field(
        ..., description="The product specification as a JSON object."
    )


class ProductValidator:
    """A class to validate a product against a feature model."""

    def __init__(self, feature_model: FeatureModel):
        self.feature_model = feature_model
        self.enabled_features: set[str] = set()
        self.input_product: Product | None = None
        self.fullspec: JsonObject | None = None

    def validate_structure(self, feature: Feature, tree: JsonValue):
        """Validate that the tree structure of the product spec is consistent with the feature model,
        without checking attribute values or group constraints."""
        if not isinstance(tree, dict):
            raise ValueError(
                f"Expected a dict for feature {feature.name}, got {type(tree)}"
            )
        feature_members = feature.members()

        # check tree names exist in feature
        for key in tree:
            if key not in feature_members:
                raise ValueError(
                    f"Unexpected field {key} in feature {feature.fullname}"
                )

        # Compute mentioned groups
        mentioned_groups = [
            g
            for g in tree.keys()
            if isinstance(feature_members.get(g), SubfeatureGroup)
        ]

        # We process each mentioned group.
        # We support two types of syntax for subfeatures.
        # First:
        #   "group1": {
        #       "subfeature1": { ... },
        #       "subfeature2": { ... },
        #   }
        # Second:
        #   "group1": ["subfeature1", "subfeature2"]
        #
        # In the first case, we change the tree to look like the second case,
        # but we move the subfeature specs to the above level, so that they can be
        # processed.
        for g in mentioned_groups:
            group = feature_members[g]
            tg = tree[g]
            if isinstance(tg, dict):
                # Check that all keys are feature names
                keys = set(tg.keys())
            elif isinstance(tg, list):
                keys = set(tg)
            else:
                raise ValueError(
                    f"Expected a dict or list for subfeature group {group.group_name} of feature {feature.fullname}, got {type(tg)}"
                )

            if not (keys <= set(f.name for f in group.members)):
                raise ValueError(
                    f"Invalid keys {keys - set(f.name for f in group.members)} in subfeature group {group.group_name} of feature {feature.fullname}"
                )

            # check that subfeatures are not configured twice
            if isinstance(tg, dict):
                if keys.intersection(set(tree.keys())):
                    raise ValueError(
                        f"Subfeatures {keys.intersection(set(tree.keys()))} of group {group.group_name} in feature {feature.fullname} are configured both as subfeatures and as direct children."
                    )

                # Take out and fix the tree
                tree |= tg
                tree[g] = list(keys)

        # Finally, we recurse to all feature specs
        for key, value in tree.items():
            member = feature_members[key]
            if isinstance(member, Feature):
                self.validate_structure(member, value)

    def select_features(self, feature: Feature, tree: JsonValue):
        """Select features based on the product spec, and mark them as enabled."""
        feature_members = feature.members()

        for group in feature.subfeatures:
            if group.rel == "mandatory":
                # All members of this group are enabled, regardless of the tree value
                tree[group.identifier] = [member.name for member in group.members]
            else:
                # Only the mentioned members of this group are enabled
                if group.identifier in tree:
                    # Explicit selection, do nothing
                    pass
                elif any(member.name in tree for member in group.members):
                    # Implicit selection, add the mentioned members to the tree
                    tree[group.identifier] = [
                        member.name for member in group.members if member.name in tree
                    ]
                elif group.default is not None:
                    # Default selection, add the default members to the tree
                    tree[group.identifier] = group.default
                else:
                    # No selection from this group!! an error, unless the group is empty
                    if len(group.members) > 0:
                        raise ValueError(
                            f"No selection for subfeature group {group.group_name} in feature {feature.fullname}"
                        )

        # Check that every feature in the tree is actually selected in its group
        # This can happen if a group is explicitly selected but some unselected feature
        # is actually mentioned in the tree, which is an error.
        for key, value in tree.items():
            member = feature_members[key]
            if isinstance(member, Feature):
                # Check that this feature is selected in its group
                if member.name not in tree[member.group.identifier]:
                    raise ValueError(
                        f"Feature {member.fullname} is mentioned in the product spec but not selected in its group {group.group_name}."
                    )

        # We should add empty specs for selected features that are not mentioned in the tree
        for group in feature.subfeatures:
            # Every group is now mentioned in the tree.
            mentioned_features = tree[group.identifier]
            for f in mentioned_features:
                if f not in tree:
                    tree[f] = {}

        # Finally, we recurse to all feature specs
        for key, value in tree.items():
            member = feature_members[key]
            if isinstance(member, Feature):
                self.select_features(member, value)

    def select_required_features(self, feature: Feature, tree: JsonValue):
        """Select required features based on the product spec, and mark them as enabled."""
        feature_members = feature.members()

        # Just add to enabled features for now.
        # When we add "requires" constraints, we will need to come back to this.
        self.enabled_features.add(feature.fullname)

        # Finally, we recurse to all feature specs
        for key, value in tree.items():
            member = feature_members[key]
            if isinstance(member, Feature):
                self.select_required_features(member, value)

    def validate_groups(self, feature: Feature, tree: JsonValue):
        """Validate that the group constraints are satisfied in the product spec."""
        feature_members = feature.members()

        # Check group constraints
        for group in feature.subfeatures:
            if group.rel == "alternative":
                if len(tree[group.identifier]) != 1:
                    raise ValueError(
                        f"In feature {feature.fullname}, exactly one member of group {group.group_name} must be selected, but got {len(tree[group.identifier])} ({tree[group.identifier]})"
                    )
            elif group.rel == "or":
                if len(tree[group.identifier]) == 0:
                    raise ValueError(
                        f"In feature {feature.fullname}, at least one member of group {group.group_name} must be selected, but got none."
                    )

            # We do not need to check mandatory and optional groups,
            # because they are already handled in the select_features step.

        # Finally, we recurse to all feature specs
        for key, value in tree.items():
            member = feature_members[key]
            if isinstance(member, Feature):
                self.validate_groups(member, value)

    def validate_attribute(
        self,
        feature: Feature,
        validator: JsonSchemaValidator,
        attr_name: str,
        value: JsonValue,
    ):
        """Validate a tree against a feature attribute."""
        try:
            validator.validate(value)
            return value
        except Exception as e:
            raise ValueError(
                f"Validation error for attribute {attr_name} of feature {feature.fullname}: {e}"
            ) from e

    def validate_attributes(self, feature: Feature, tree: JsonValue):
        """Validate that the attribute constraints are satisfied in the product spec."""
        feature_members = feature.members()

        # Check attribute constraints
        for attr_name in feature.attributes:
            if attr_name in tree:
                validator = feature_members[attr_name]
                value = tree[attr_name]
                self.validate_attribute(feature, validator, attr_name, value)
            else:
                # Check if this attribute is required (i.e., has no default value)
                if "default" not in validator:
                    raise ValueError(
                        f"Missing required attribute '{attr_name}' in feature {feature.fullname}"
                    )
                else:
                    # Add the default value to the tree
                    tree[attr_name] = validator["default"]

        # Finally, we recurse to all feature specs
        for key, value in tree.items():
            member = feature_members[key]
            if isinstance(member, Feature):
                self.validate_attributes(member, value)

    def validate(self, product: Product):
        """Validate a product against a feature model."""

        self.enabled_features = set()
        self.input_product = product
        root = self.feature_model.root
        spec = deepcopy(product.spec)

        # First, validate names in the spec
        self.validate_structure(root, spec)
        self.select_features(root, spec)
        self.select_required_features(root, spec)
        self.validate_groups(root, spec)
        self.validate_attributes(root, spec)

        # Process the root feature, which is always enabled
        self.fullspec = {root.name: spec}

        return self.fullspec
