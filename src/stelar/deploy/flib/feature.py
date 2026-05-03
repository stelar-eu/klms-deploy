#
# Features are basic building blocks of feature models.
#
from __future__ import annotations

from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

AttrValue = str | int | float | bool | None

class Feature(BaseModel):
    """A feature is a basic building block of a feature model."""

    # Names are feature identifiers.
    name: str
    
    # tags are used to categorize features. A feature can have multiple tags, and a tag can be associated with multiple features.
    tags: set[str] = Field(default_factory=set, repr=False)

    # Descriptions provide additional information about a feature.
    description: str = Field(default="", repr=False)
    
    # Attributes are key-value pairs that provide additional information about a feature.
    attr: dict[str, AttrValue] = Field(default_factory=dict, repr=False)

    # Subfeatures are orgainized in groups.
    subfeatures: list[SubfeatureGroup] = Field(default_factory=list, repr=False)

    # The feature model that this feature belongs to. This is only set after the feature is added to a feature model.
    fmodel: FeatureModel | None = Field(default=None, repr=False, exclude=True)

    # The parent feature of this feature. This is only set after the feature is added 
    # to a feature model, and is None for the root feature.
    parent: Feature | None = Field(default=None, repr=False, exclude=True)

    model_config = ConfigDict(extra="forbid")

class SubfeatureGroup(BaseModel):
    """A subfeature group is a group of features that are sibling-subfeatures of some parent feature,
       with a common relationship.

    There are four types of relationships:
    - mandatory: all features in the group must be selected if the parent feature is selected.
    - optional: any feature in the group can be selected if the parent feature is selected.
    - alternative: exactly one feature in the group must be selected if the parent feature is selected.
    - or: at least one feature in the group must be selected if the parent feature is
       
    A subfeature group also posesses a name, used to identify the group, or it may be None.
    If a name is provided, it must be unique within the parent feature.
    """

    # the type of relationship
    rel: Literal["mandatory", "optional", "alternative", "or"]

    # The name of the subfeature group.
    group_name: str | None = Field(default=None)

    # The features that belong to this subfeature group.
    members: list[Feature] = Field(default_factory=list, repr=False)

    model_config = ConfigDict(extra="forbid")

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
                for subfeature in group.members:
                    _rebuild(subfeature, feature, model)

        _rebuild(self.root, None, self)
        return self


Feature.model_rebuild()



def load_feature_model_from_dict(data: dict) -> FeatureModel:
    """Load a feature model from a dictionary."""
    fm = FeatureModel.model_validate(data)
    #fm.rebuild()
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
    

