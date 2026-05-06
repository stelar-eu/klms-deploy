from pyexpat import model

import pytest

from stelar.deploy.models.feature import (
    Feature,
    FeatureModel,
    SubfeatureGroup,
    AttributeValidator,
)


def test_feature_model():
    # Create a feature model
    root = Feature(name="root")
    fm = FeatureModel(name="fm", root=root)

    # Create some features
    f1 = Feature(name="f1")
    f2 = Feature(name="f2")
    f3 = Feature(name="f3")

    # Add features to the feature model
    root.subfeatures.append(SubfeatureGroup(rel="mandatory", members=[f1, f2]))
    root.subfeatures.append(SubfeatureGroup(rel="optional", members=[f3]))

    # Check that the features are added correctly
    assert f1 in root.subfeatures[0].members
    assert f2 in root.subfeatures[0].members
    assert f3 in root.subfeatures[1].members


def check_parent_and_model(
    feature: Feature, parent: Feature | None, fmodel: FeatureModel
):
    assert feature.parent == parent, f"Feature parent error: {feature}"
    assert (
        feature.fmodel == fmodel
    ), f"Feature {feature.name} has fmodel {feature.fmodel.name if feature.fmodel else None}, expected {fmodel.name if fmodel else None}"
    for group in feature.subfeatures:
        for subfeature in group.members:
            check_parent_and_model(subfeature, feature, fmodel)


def test_feature_model_load():
    # Load a feature model from a dictionary
    data = {
        "name": "fm",
        "root": {
            "name": "root",
            "subfeatures": [
                {"rel": "mandatory", "members": [{"name": "f1"}, {"name": "f2"}]},
                {"rel": "optional", "members": [{"name": "f3"}]},
            ],
        },
    }
    fm = FeatureModel.model_validate(data)
    assert fm.name == "fm"
    assert fm.root.name == "root"
    assert fm.root.subfeatures[0].rel == "mandatory"
    assert fm.root.subfeatures[0].members[0].name == "f1"
    assert fm.root.subfeatures[0].members[1].name == "f2"
    assert fm.root.subfeatures[1].rel == "optional"
    assert fm.root.subfeatures[1].members[0].name == "f3"

    # check that the parent and model attributes are set correctly
    check_parent_and_model(fm.root, None, fm)


def test_feature_model_load_yaml():
    # Load a feature model from a YAML string
    import yaml

    data = """
    name: fm
    root:
      name: root
      subfeatures:
        - rel: mandatory
          members:
            - name: f1
            - name: f2
        - rel: optional
          members:
            - name: f3
    """
    fm = FeatureModel.model_validate(yaml.safe_load(data))
    assert fm.name == "fm"
    assert fm.root.name == "root"
    assert fm.root.subfeatures[0].rel == "mandatory"
    assert fm.root.subfeatures[0].members[0].name == "f1"
    assert fm.root.subfeatures[0].members[1].name == "f2"
    assert fm.root.subfeatures[1].rel == "optional"
    assert fm.root.subfeatures[1].members[0].name == "f3"
    # check that the parent and model attributes are set correctly
    check_parent_and_model(fm.root, None, fm)


def test_stelar_yaml():
    # Test that the loaded STELAR f.m. is correct
    from stelar.deploy import feature_model

    assert feature_model.name == "STELAR"
    assert feature_model.root.name == "klms"
    check_parent_and_model(feature_model.root, None, feature_model)


def test_his_model(his_model):
    assert his_model.name == "HIS"
    assert his_model.root.name == "his"
    check_parent_and_model(his_model.root, None, his_model)


def test_validation_empty():
    # Test that invalid feature models raise validation errors
    with pytest.raises(ValueError):
        FeatureModel.model_validate({})


model_missing_name = {"root": {"name": "root"}}


def test_validation_missing_name():
    with pytest.raises(ValueError):
        FeatureModel.model_validate(model_missing_name)


model_with_extra_field = {
    "name": "fm",
    "root": {
        "name": "root",
    },
    "extra": "field",
}


def test_validation_extra_field():
    with pytest.raises(ValueError):
        FeatureModel.model_validate(model_with_extra_field)


model_feature_missing_name = {"name": "fm", "root": {"subfeatures": []}}


def test_validation_feature_missing_name():
    with pytest.raises(ValueError):
        FeatureModel.model_validate(model_feature_missing_name)


model_feature_extra_field = {"name": "fm", "root": {"name": "root", "extra": "field"}}


def test_validation_feature_extra_field():
    with pytest.raises(ValueError):
        FeatureModel.model_validate(model_feature_extra_field)


model_subfeature_group_missing_rel = {
    "name": "fm",
    "root": {"name": "root", "subfeatures": [{"members": [{"name": "f1"}]}]},
}


def test_validation_subfeature_group_missing_rel():
    with pytest.raises(ValueError):
        FeatureModel.model_validate(model_subfeature_group_missing_rel)


model_subfeature_group_extra_field = {
    "name": "fm",
    "root": {
        "name": "root",
        "subfeatures": [
            {"rel": "mandatory", "members": [{"name": "f1"}], "extra": "field"}
        ],
    },
}


def test_validation_subfeature_group_extra_field():
    with pytest.raises(ValueError):
        FeatureModel.model_validate(model_subfeature_group_extra_field)


def test_feature_path_names(his_model):
    # Test that the path names of the features in the HIS model are correct
    assert his_model.root.path_names == ["his"]

    for sfg in his_model.root.subfeatures:
        for feature in sfg.members:
            assert feature.path_names == ["his", feature.name]


def test_feature_fullnames(his_model):
    # Test that the full names of the features in the HIS model are correct
    assert his_model.root.fullname == "his"

    for sfg in his_model.root.subfeatures:
        for feature in sfg.members:
            assert feature.fullname == f"his.{feature.name}"


def test_feature_model_features(his_model):
    # Test that the features property of the feature model returns all features
    features = his_model.features
    assert len(features) == 15
    names = [f.name for f in features]
    expected_names = [
        "his",
        "supervision",
        "flood",
        "fire",
        "intrusion",
        "control",
        "lighting",
        "temperature",
        "appliances",
        "services",
        "video_on_demand",
        "internet_access",
        "powerline",
        "wifi",
        "ADSL",
    ]
    for name in expected_names:
        assert name in names, f"Feature {name} not found in features"


def test_feature_model_default_selection_validation():
    # Test that invalid default selections raise validation errors
    with pytest.raises(ValueError):
        FeatureModel.model_validate(
            {
                "name": "fm",
                "root": {
                    "name": "root",
                    "subfeatures": [
                        {
                            "rel": "alternative",
                            "default": ["f3"],
                            "members": [{"name": "f1"}, {"name": "f2"}],
                        }
                    ],
                },
            }
        )
    with pytest.raises(ValueError):
        FeatureModel.model_validate(
            {
                "name": "fm",
                "root": {
                    "name": "root",
                    "subfeatures": [
                        {
                            "rel": "or",
                            "default": [],
                            "members": [{"name": "f1"}, {"name": "f2"}],
                        }
                    ],
                },
            }
        )


def test_feature_model_alternative_group_default_validation():
    # Test that an alternative group with multiple default
    # selections raises a validation error
    with pytest.raises(ValueError):
        FeatureModel.model_validate(
            {
                "name": "fm",
                "root": {
                    "name": "root",
                    "subfeatures": [
                        {
                            "rel": "alternative",
                            "default": ["f1", "f2"],
                            "members": [{"name": "f1"}, {"name": "f2"}],
                        }
                    ],
                },
            }
        )


def test_feature_model_illegal_feature_name():
    # Test that illegal feature names raise validation errors

    bad_names = [
        "1f1",
        "f-1",
        "f 1",
        "f.1",
        "f/1",
        "f\\1",
        "f@1",
        "f#1",
        "f$1",
        "f%1",
        "f^1",
        "f&1",
        "f*1",
        "f(1)",
        "f)1",
        "f+1",
        "f=1",
        "f{1}",
        "f}1",
        "f[1]",
        "f]1",
        "f|1",
        "f<1>",
        "",
        " ",
        "f\n1",
        "f\t1",
    ]
    for name in bad_names:
        with pytest.raises(ValueError):
            FeatureModel.model_validate({"name": "fm", "root": {"name": name}})


def test_feature_attribute_validation():
    # Test that the attr field of a feature is validated correctly
    f = Feature.model_validate(
        {
            "name": "f",
            "attributes": {
                "attr1": {
                    "type": "string",
                    "default": "hello",
                },
                "attr2": {"type": "number"},
                "attr3": {"type": "boolean"},
            },
        }
    )

    for attr_name in ["attr1", "attr2", "attr3"]:
        AttributeValidator.check_schema(f.attributes[attr_name])


def test_feature_attribute_bad_name():
    # Test that invalid attribute names raise validation errors
    for bad_name in ["1attr", "attr-1", "attr 1", "attr.1"]:
        with pytest.raises(ValueError):
            Feature.model_validate(
                {
                    "name": "f",
                    "attributes": {
                        bad_name: {"type": "string"},
                    },
                }
            )


def test_feature_attribute_bad_schema():
    # Test that invalid attribute schemas raise validation errors
    with pytest.raises(ValueError):
        Feature.model_validate(
            {
                "name": "f",
                "attributes": {
                    "attr1": {"type": "unknown_type"},
                },
            }
        )


def test_feature_members(his_model):
    # Test that the members property of a subfeature group returns the correct features
    fmembers = his_model.root.members()

    expected_names = [
        "system_name",
        "manufacturer",
        "supervision",
        "control",
        "services",
        "[0]",
        "[1]",
    ]

    actual_names = fmembers.keys()
    assert set(actual_names) == set(expected_names)


def test_subfeature_group_name_validation():
    fm_in = {
        "name": "fm",
        "root": {
            "name": "root",
            "subfeatures": [
                {
                    "rel": "mandatory",
                    "group_name": "group1",
                    "members": [{"name": "f1"}, {"name": "f2"}],
                },
                {
                    "rel": "optional",
                    "members": [{"name": "f3"}],
                },
            ],
        },
    }

    # Test that valid group names are accepted and assigned identifiers
    fm = FeatureModel.model_validate(fm_in)
    assert fm.root.subfeatures[0].group_name == "group1"
    assert fm.root.subfeatures[1].group_name is None
    assert fm.root.subfeatures[0].identifier == "group1"
    assert fm.root.subfeatures[1].identifier == "[1]"

    # Test that non-unique group names raise validation errors
    fm_in["root"]["subfeatures"][1]["group_name"] = "group1"
    with pytest.raises(ValueError):
        FeatureModel.model_validate(fm_in)

    # Test that invalid group names raise validation errors
    for bad_name in ["1group", "group-1", "group 1", "group.1"]:
        fm_in["root"]["subfeatures"][1]["group_name"] = bad_name
        with pytest.raises(ValueError):
            FeatureModel.model_validate(fm_in)
