#
# Products are tree-like structures that represent the selected and configured
# features for a deployment. They are generated from the feature model and the
# selected features, and they are used to generate the deployment configuration.
# A product is a member of a product line defined by a feature model.
#

from copy import deepcopy
from typing import Any
from collections import defaultdict

from pydantic import BaseModel, JsonValue, Field

from .feature import (
    Feature,
    FeatureModel,
    SubfeatureGroup,
    AttributeValidator,
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


class ProductValidationFailure(ValueError):
    """Raised when product validation fails."""

    def __init__(self, message: str, validation_errors: dict[str, list[str]]):
        super().__init__(message)
        self.validation_errors = validation_errors

    def __str__(self):
        from io import StringIO

        out = StringIO()
        print(super().__str__(), file=out)
        print("Validation errors:", file=out)
        for feature, errors in self.validation_errors.items():
            print(f"  {feature}:", file=out)
            for error in errors:
                print(f"    - {error}", file=out)
        return out.getvalue()


class ProductValidator:
    """A class to validate a product against a feature model."""

    def __init__(self, feature_model: FeatureModel):
        self.feature_model = feature_model
        self.enabled_features: set[str] = set()
        self.input_product: Product | None = None
        self.fullspec: JsonObject | None = None
        self.validation_errors: defaultdict[str, list[str]] = defaultdict(list)

    def report_error(self, feature: Feature, message: str):
        """Report a validation error for a feature."""
        self.validation_errors[feature.fullname].append(message)

    def _validate_structure(self, feature: Feature, tree: JsonObject):
        """Validate that the tree structure of the product spec is consistent with
        the feature model, without checking attribute values or group constraints."""
        if not isinstance(tree, dict):
            raise ValueError(
                f"Expected a dict for feature {feature.name}, got {type(tree)}"
            )
        all_members = feature.members()

        # check tree names exist in feature
        for key in tree:
            if key not in all_members:
                self.report_error(feature, f"Unexpected field {key}")

        group_members = feature.group_members()

        # Compute mentioned groups
        mentioned_groups = [g for g in tree.keys() if g in group_members]

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
            group: SubfeatureGroup = group_members[g]
            tg = tree[g]
            if isinstance(tg, dict):
                # Check that all keys are feature names
                keys = set(tg.keys())
            elif isinstance(tg, list):
                keys = set(tg)
            else:
                self.report_error(
                    feature,
                    (
                        f"Expected a dict or list for subfeature group {group.identifier},"
                        f" got {type(tg)}"
                    ),
                )
                keys = set()

            if not (keys <= set(f.name for f in group.members)):
                self.report_error(
                    feature,
                    (
                        f"Invalid keys {keys - set(f.name for f in group.members)} "
                        f"in subfeature group {group.identifier}"
                    ),
                )

            # check that subfeatures are not configured twice
            if isinstance(tg, dict):
                if keys.intersection(set(tree.keys())):
                    self.report_error(
                        feature,
                        (
                            f"Subfeatures {keys.intersection(set(tree.keys()))} "
                            f"of group {group.identifier} are configured both as "
                            f"subfeatures and as direct children."
                        ),
                    )

                # Take out and fix the tree
                tree |= tg
                tree[g] = list(keys)

        # Finally, we recurse to all feature specs
        feature_members = feature.feature_members()
        for key, value in tree.items():
            if key in feature_members:
                self._validate_structure(feature_members[key], value)

    def _select_features(self, feature: Feature, tree: JsonObject):
        """Select features based on the product spec, and mark them as enabled."""
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
                    # No selection for this group!! an error, unless the group is empty
                    if len(group.members) > 0:
                        self.report_error(
                            feature,
                            f"No selection for subfeature group {group.identifier}",
                        )

        # Check that every feature in the tree is actually selected in its group
        # This can happen if a group is explicitly selected but some unselected feature
        # is actually mentioned in the tree, which is an error.

        feature_members = feature.members()

        for key, value in tree.items():
            member = feature_members[key]
            if isinstance(member, Feature):
                # Check that this feature is selected in its group
                if (
                    member.group is not None
                    and member.name not in tree[member.group.identifier]
                ):
                    self.report_error(
                        feature,
                        (
                            f"Feature {member.fullname} is mentioned in the product spec"
                            f" but not selected in its group {member.group.identifier}."
                        ),
                    )

        # We should add empty specs for selected features that are not mentioned in the tree
        for group in feature.subfeatures:

            # Every group is now mentioned in the tree,
            # unless an error has occurred, in which case we skip
            # this group.
            mentioned_features = tree.get(group.identifier)
            if mentioned_features is None:
                self.report_error(
                    feature,
                    f"Subfeature group {group.identifier} not mentioned in the product spec",
                )
                continue

            for f in mentioned_features:
                if f not in tree:
                    tree[f] = {}

        # Finally, we recurse to all feature specs
        for key, value in tree.items():
            member = feature_members[key]
            if isinstance(member, Feature):
                self._select_features(member, value)

    def _select_required_features(self, feature: Feature, tree: JsonObject):
        """Select required features based on the product spec, and mark them as enabled."""
        feature_members = feature.members()

        # Just add to enabled features for now.
        # When we add "requires" constraints, we will need to come back to this.
        self.enabled_features.add(feature.fullname)

        # Finally, we recurse to all feature specs
        for key, value in tree.items():
            member = feature_members[key]
            if isinstance(member, Feature):
                self._select_required_features(member, value)

    def _validate_groups(self, feature: Feature, tree: JsonObject):
        """Validate that the group constraints are satisfied in the product spec."""
        feature_members = feature.members()

        # Check group constraints
        for group in feature.subfeatures:
            if group.rel == "alternative":
                if len(tree[group.identifier]) != 1:
                    self.report_error(
                        feature,
                        (
                            f"Exactly one member of group {group.identifier} must be"
                            f" selected, but got {len(tree[group.identifier])}"
                            f" ({tree[group.identifier]})"
                        ),
                    )
            elif group.rel == "or":
                if len(tree[group.identifier]) == 0:
                    self.report_error(
                        feature,
                        (
                            f"In feature {feature.fullname}, at least one member of group"
                            f" {group.identifier} must be selected, but got none."
                        ),
                    )

            # We do not need to check mandatory and optional groups,
            # because they are already handled in the select_features step.

        # Finally, we recurse to all feature specs
        for key, value in tree.items():
            member = feature_members[key]
            if isinstance(member, Feature):
                self._validate_groups(member, value)

    def _validate_attribute(
        self,
        feature: Feature,
        validator: AttributeValidator,
        attr_name: str,
        value: JsonValue,
    ):
        """Validate a tree against a feature attribute."""
        try:
            validator.validate(value)
        except Exception as e:
            self.report_error(
                feature,
                f"Validation error for attribute {attr_name}: {e}",
            )
        return value

    def _validate_attributes(self, feature: Feature, tree: JsonObject):
        """Validate that the attribute constraints are satisfied in the product spec."""

        # Check attribute constraints
        for attr_name, validator in feature.attribute_members().items():
            if attr_name in tree:
                value = tree[attr_name]
                self._validate_attribute(feature, validator, attr_name, value)
            else:
                # Check if this attribute is required (i.e., has no default value)
                if isinstance(validator.schema, dict) and "default" in validator.schema:
                    # Add the default value to the tree
                    tree[attr_name] = validator.schema["default"]
                else:
                    self.report_error(
                        feature, f"Missing required attribute '{attr_name}'"
                    )

        # Finally, we recurse to all feature specs
        subfeatures = feature.feature_members()
        for key, value in tree.items():
            if key in subfeatures:
                self._validate_attributes(subfeatures[key], value)

    def _raise_if_errors(self):
        """Raise a ProductValidationFailure if there are any validation errors."""
        if self.validation_errors:
            raise ProductValidationFailure(
                "Product validation failed", dict(self.validation_errors)
            )

    def _prepare_validation(self):
        """Prepare for validation by clearing the enabled features and validation errors."""
        self.enabled_features.clear()
        self.validation_errors.clear()
        self.input_product = None
        self.fullspec = None

    def validate(self, product: Product):
        """Validate a product against a feature model."""

        self._prepare_validation()
        self.enabled_features = set()
        self.input_product = product
        root = self.feature_model.root
        spec = deepcopy(product.spec)

        # Perform the validation steps.
        self._validate_structure(root, spec)
        self._raise_if_errors()

        self._select_features(root, spec)
        self._raise_if_errors()

        self._select_required_features(root, spec)
        self._raise_if_errors()

        self._validate_groups(root, spec)
        self._raise_if_errors()

        self._validate_attributes(root, spec)
        self._raise_if_errors()

        # Process the root feature, which is always enabled
        self.fullspec = {root.name: spec}
        return self.fullspec
