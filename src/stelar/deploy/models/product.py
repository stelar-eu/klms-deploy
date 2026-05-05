#
# Products are tree-like structures that represent the selected and configured features for a deployment. They are generated from the feature model and the selected features, and they are used to generate the deployment configuration.
# A product is a member of a product line defined by a feature model.
#

from typing import Any

from stelar.deploy.models.feature import Feature, FeatureModel

JsonObject = dict[str, Any]


class ProductValidator:
    """A class to validate a product against a feature model."""

    def __init__(self, feature_model: FeatureModel):
        self.feature_model = feature_model

    def _validate_feature(self, feature: Feature, tree: JsonObject):
        """Validate a tree against a single feature."""

        feature_members = feature.members()

    def validate(self, product: JsonObject):
        """Validate a product against a feature model."""
        root_name = self.feature_model.root.name
        if root_name not in product:
            raise ValueError(f"Product must contain the root feature '{root_name}'")
        self._validate_feature(self.feature_model.root, product.get(root_name))
