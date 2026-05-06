#
# Features are basic building blocks of feature models.
#
from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable, Iterator, Literal, Self, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from jsonschema.validators import Draft202012Validator as AttributeValidator
from referencing.jsonschema import Schema as AttributeSchema

REGEX_IDENTIFIER = r"^[a-zA-Z_][a-zA-Z0-9_]*$"


def _duplicate_names(names: Iterable[str]) -> set[str]:
    """Check if the names in the iterable are unique."""
    dup = set()
    seen = set()
    for name in names:
        if name in seen:
            dup.add(name)
        seen.add(name)
    return dup


class Feature(BaseModel):
    """A feature is a basic building block of a feature model.

    Feature properties:
    - A feature has a name that must be a valid identifier.
    - A feature can have multiple tags.
    - A feature can have a description.
    - A feature can have attributes. Each attribute is specified by a name (identifier) and a JSON schema.
    - A feature can have subfeatures. Subfeatures are organized in groups.

    All members of a feature (attributes, subfeature groups, and child features) must have unique names
    within the feature. Group names must also be unique within the feature if they are not None.

    """

    # Names are feature identifiers.
    name: str = Field(pattern=REGEX_IDENTIFIER)

    # tags are used to categorize features. A feature can have multiple tags, and a tag can be associated with multiple features.
    tags: set[str] = Field(default_factory=set, repr=False)

    # Descriptions provide additional information about a feature.
    description: str = Field(default="", repr=False)

    # Attributes are key-value pairs that provide additional information
    # about a feature. In the feature model, attributes are defined
    # by a name and a JSON schema.
    attributes: dict[str, AttributeSchema] = Field(default_factory=dict, repr=False)

    # Subfeatures are orgainized in groups.
    subfeatures: list[SubfeatureGroup] = Field(default_factory=list, repr=False)

    # The feature model that this feature belongs to. This is only set after the feature is added to a feature model.
    fmodel: FeatureModel | None = Field(default=None, repr=False, exclude=True)

    # The parent feature of this feature. This is only set after the feature is added
    # to a feature model, and is None for the root feature.
    parent: Feature | None = Field(default=None, repr=False, exclude=True)

    # The group that this feature belongs to. This is only set after the feature is added to a feature model,
    # and is None for the root feature.
    group: Optional[SubfeatureGroup] = Field(default=None, repr=False, exclude=True)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def check_subfeature_groups(self) -> Self:
        """Check if the subfeature groups of this feature are valid."""
        if _duplicate_names(
            group.group_name
            for group in self.subfeatures
            if group.group_name is not None
        ):
            raise ValueError(
                f"Group names are not unique within the feature {self.name}."
            )
        return self

    @model_validator(mode="after")
    def check_children_names(self) -> Self:
        """Check if the child feature names are unique within this feature."""
        if _duplicate_names(child.name for child in self.children):
            raise ValueError(
                f"Child feature names are not unique within feature {self.name}."
            )
        return self

    @model_validator(mode="after")
    def check_attribute_names(self) -> Self:
        """Check if the attribute names are unique within this feature."""
        # Check that attribute names are not group names
        for attr_name in self.attributes:
            if not re.match(REGEX_IDENTIFIER, attr_name):
                raise ValueError(
                    f"Attribute name {attr_name} is not a valid identifier in feature {self.name}."
                )

        for attr_name, attr_spec in self.attributes.items():
            try:
                AttributeValidator.check_schema(attr_spec)
            except Exception as e:
                raise ValueError(
                    f"Attribute {attr_name} in feature {self.name} has an invalid JSON schema: {e}"
                ) from e

        if any(group.group_name in self.attributes for group in self.subfeatures):
            raise ValueError(
                f"Attribute names cannot be the same as group names within feature {self.name}."
            )

        return self

    @property
    def children(self) -> Iterator[Feature]:
        """Get the child features of this feature."""
        for group in self.subfeatures:
            for subfeature in group.members:
                yield subfeature

    @property
    def path_names(self) -> list[str]:
        """Get the path names from the root to this feature."""
        path = []
        cur = self
        while cur is not None:
            path.append(cur.name)
            cur = cur.parent
        path.reverse()
        return path

    @property
    def fullname(self) -> str:
        """Get the full name of this feature, which is the path names joined by dots."""
        return ".".join(self.path_names)

    def attribute_members(self) -> dict[str, AttributeValidator]:
        """Get the attribute members of this feature."""
        return {
            attr_name: AttributeValidator(attr_spec)
            for attr_name, attr_spec in self.attributes.items()
        }

    def group_members(self) -> dict[str, SubfeatureGroup]:
        """Get the group members of this feature."""
        return {group.identifier: group for group in self.subfeatures}

    def feature_members(self) -> dict[str, Feature]:
        """Get the members of this feature, which include its child features and subfeature groups."""
        return {feature.name: feature for feature in self.children}

    def members(self) -> dict[str, Feature | SubfeatureGroup | AttributeValidator]:
        """Get the members of this feature, which include its child features and
        subfeature groups."""
        return self.feature_members() | self.group_members() | self.attribute_members()

    def get(self, name: str, default: Feature | None = None) -> Feature | None:
        """Get a subfeature by name."""
        for group in self.subfeatures:
            for subfeature in group.members:
                if subfeature.name == name:
                    return subfeature
        return default

    def subfeature(self, name: str) -> Feature:
        """Get a subfeature by name."""
        sf = self.get(name)
        if sf is None:
            raise KeyError(f"Subfeature {name} not found in feature {self.name}.")
        return sf


class SubfeatureGroup(BaseModel):
    """A subfeature group is a group of features that are sibling-subfeatures of some parent feature,
       with a common relationship.

    There are four types of relationships:
    - mandatory: all features in the group must be selected if the parent feature is selected.
    - optional: any feature in the group can be selected if the parent feature is selected.
    - alternative: exactly one feature in the group must be selected if the parent feature is selected.
    - or: at least one feature in the group must be selected if the parent feature is

    A subfeature group also posesses a name, used to identify the group,
    or it may be None. If a name is provided, it must be unique within
    the parent feature.
    """

    # the type of relationship
    rel: Literal["mandatory", "optional", "alternative", "or"]

    # The name of the subfeature group.
    group_name: str | None = Field(default=None)

    # default selection for this subfeature group
    default: list[str] | None = Field(default=None, repr=False)

    # The features that belong to this subfeature group.
    members: list[Feature] = Field(default_factory=list, repr=False)

    # The parent feature. This is only set after the featureis added to a feature model.
    parent: Feature | None = Field(default=None, repr=False, exclude=True)

    # The index into the subfeatures list
    @property
    def index(self) -> int:
        if self.parent is None:
            raise RuntimeError(
                "Subfeature index cannot be determined on incomplete model."
            )
        return self.parent.subfeatures.index(self)

    model_config = ConfigDict(extra="forbid")

    @property
    def identifier(self) -> str:
        """Get the identifier of this subfeature group, which is its name if it has one, or its index otherwise."""
        if self.group_name is not None:
            return self.group_name
        else:
            return f"[{self.index}]"

    def select(self, name: str) -> Feature | None:
        """Select a feature from this subfeature group by name."""
        for member in self.members:
            if member.name == name:
                return member
        return None

    @model_validator(mode="after")
    def check_membership(self) -> Self:
        """Check if the members of this subfeature group are valid according to the relationship type."""
        if self.rel in ["or", "alternative"] and len(self.members) == 0:
            raise ValueError(
                f"{self.rel.capitalize()} group must have at least one member."
            )
        return self

    @model_validator(mode="after")
    def check_default_selection(self) -> Self:
        """Check if the default selection is valid according to the relationship type."""
        if self.default is None:
            return self
        if self.rel == "mandatory":
            raise ValueError("Default selection is not allowed for mandatory group.")
        member_names = {feature.name for feature in self.members}
        for name in self.default:
            if name not in member_names:
                raise ValueError(
                    f"Default selection {name} is not a member of the subfeature group."
                )
        if self.rel == "alternative" and len(self.default) != 1:
            raise ValueError(
                "Default selection for alternative group must contain exactly one feature."
            )
        if self.rel == "or" and len(self.default) < 1:
            raise ValueError(
                "Default selection for or group must contain at least one feature."
            )
        return self

    @model_validator(mode="after")
    def check_group_name(self) -> Self:
        """Check if the group name is a valid identifier."""
        if self.group_name is not None and not re.match(
            REGEX_IDENTIFIER, self.group_name
        ):
            raise ValueError(f"Group name {self.group_name} is not a valid identifier.")
        return self

    @model_validator(mode="after")
    def check_member_names(self) -> Self:
        """Check if the member names are unique within the subfeature group."""
        if _duplicate_names(feature.name for feature in self.members):
            raise ValueError(
                f"Feature names are not unique within the subfeature group."
            )
        return self


class FeatureModel(BaseModel):
    """A feature model consists of a feature tree and additional relationships."""

    # The name of the feature model.
    name: str

    # The root feature of the feature model.
    root: Feature

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def rebuild(self) -> Self:
        """Rebuild the feature model.

        This should be called after any modifications to the feature model.
        It connects the features in the feature model by setting the parent
        and fmodel attributes of each feature.
        """

        def _rebuild(feature: Feature, parent: Feature | None, model: FeatureModel):
            feature.parent = parent
            feature.fmodel = model
            for group in feature.subfeatures:
                group.parent = feature
                for subfeature in group.members:
                    subfeature.group = group
                    _rebuild(subfeature, feature, model)

        _rebuild(self.root, None, self)
        return self

    @property
    def features(self) -> list[Feature]:
        """Get all features in the feature model."""
        result = []

        def _dfs(feature: Feature, result: list[Feature]):
            result.append(feature)
            for group in feature.subfeatures:
                for subfeature in group.members:
                    _dfs(subfeature, result)

        _dfs(self.root, result)
        return result


Feature.model_rebuild()


def load_feature_model_from_dict(data: dict) -> FeatureModel:
    """Load a feature model from a dictionary."""
    fm = FeatureModel.model_validate(data)
    # fm.rebuild()
    return fm


def load_feature_model(file_path: str | Path) -> FeatureModel:
    """Load a feature model from a file."""
    if isinstance(file_path, str):
        file_path = Path(file_path)

    if file_path.suffix == ".json":
        import json

        with open(file_path, "r") as f:
            data = json.load(f)
    elif file_path.suffix in [".yaml", ".yml"]:
        import yaml

        with open(file_path, "r") as f:
            data = yaml.safe_load(f)
    else:
        raise ValueError(f"Unsupported file format: {file_path}")
    return load_feature_model_from_dict(data)


def save_feature_model(feature_model: FeatureModel, file_path: str | Path) -> None:
    """Save a feature model to a file."""
    if isinstance(file_path, str):
        file_path = Path(file_path)

    if file_path.suffix == ".json":
        import json

        with open(file_path, "w") as f:
            json.dump(feature_model.model_dump(), f, indent=4)
    elif file_path.suffix in [".yaml", ".yml"]:
        import yaml

        with open(file_path, "w") as f:
            yaml.safe_dump(feature_model.model_dump(), f)
    else:
        raise ValueError(f"Unsupported file format: {file_path}")
