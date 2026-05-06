import pytest
from stelar.deploy.models.product import (
    Product,
    ProductValidator,
    ProductValidationFailure,
)
from stelar.deploy.models.feature import Feature, FeatureModel


def check_fullspec(feature: Feature, fspec: dict):
    # Check that the full spec contains all features in the model,
    # with values filled in.

    # check attributes
    for attr_name, validator in feature.attribute_members().items():
        assert attr_name in fspec
        try:
            validator.validate(fspec[attr_name])
        except Exception:
            assert (
                False
            ), f"Attribute '{attr_name}' failed validation with value {fspec[attr_name]}: {validator.schema}"

    # check that every group is mentioned and every selected subfeature is mentioned
    subfeatures = []
    for gid, group in feature.group_members().items():
        assert gid in fspec
        assert isinstance(fspec[gid], list)
        group_member_names = set(member.name for member in group.members)
        for subfeature_name in fspec[gid]:
            assert subfeature_name in group_member_names
            assert subfeature_name in fspec
            subfeatures.append(subfeature_name)

    # recurse
    for subfeature_name in subfeatures:
        subfeature = feature.subfeature(subfeature_name)
        check_fullspec(subfeature, fspec[subfeature_name])


def test_product(his_model: FeatureModel):
    # Test that a product validates successfully and its
    # full spec is correctly generated with default values filled in.
    p = Product(
        spec={
            "system_name": "HIS",
            "supervision": {
                "flood": {},
            },
            "services": {"internet_access": {}},
        }
    )  # select this implicitly

    fspec = ProductValidator(his_model).validate(p)
    check_fullspec(his_model.root, fspec[his_model.root.name])


@pytest.fixture
def his_validator(his_model: FeatureModel):
    return ProductValidator(his_model)


def test_empty_product(his_validator: ProductValidator):
    with pytest.raises(ProductValidationFailure) as exc_info:
        his_validator.validate(Product(spec={}))


def test_product_missing_attribute(his_validator: ProductValidator):
    with pytest.raises(ProductValidationFailure) as exc_info:
        his_validator.validate(
            Product(
                spec={
                    "supervision": {
                        "flood": {},
                    },
                    "services": {"internet_access": {}},
                }
            )
        )


def test_product_missing_subfeature(his_validator: ProductValidator):
    with pytest.raises(ProductValidationFailure) as exc_info:
        his_validator.validate(
            Product(
                spec={
                    "system_name": "HIS",
                    "supervision": {
                        # missing flood
                    },
                    "services": {"internet_access": {}},
                }
            )
        )

    with pytest.raises(ProductValidationFailure) as exc_info:
        his_validator.validate(
            Product(
                spec={
                    "system_name": "HIS",
                    "supervision": {
                        "flood": {},
                    },
                    # missing services
                }
            )
        )


def test_product_extra_field(his_validator: ProductValidator):
    with pytest.raises(ProductValidationFailure) as exc_info:
        his_validator.validate(
            Product(
                spec={
                    "system_name": "HIS",
                    "supervision": {
                        "flood": {},
                    },
                    "services": {"internet_access": {}},
                    "extra_attr": "value",  # extra attribute not in model
                }
            )
        )


def test_product_extra_subfeature(his_validator: ProductValidator):
    with pytest.raises(ProductValidationFailure) as exc_info:
        his_validator.validate(
            Product(
                spec={
                    "system_name": "HIS",
                    "supervision": {
                        "flood": {},
                        "extra_subfeature": {},  # extra subfeature not in model
                    },
                    "services": {"internet_access": {}},
                }
            )
        )
