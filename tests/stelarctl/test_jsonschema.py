# Test jsonschema validation of feature attributes.
#

from stelar.deploy.models.feature import FeatureModel
from stelar.deploy.models.feature import AttributeValidator


def test_jsonschema_validation(his_model: FeatureModel):

    fmembers = his_model.root.members()

    system_name = fmembers["system_name"]
    manufacturer = fmembers["manufacturer"]

    assert isinstance(system_name, AttributeValidator)
    assert isinstance(manufacturer, AttributeValidator)

    assert system_name.schema == {"type": "string"}
    assert manufacturer.schema == {"type": "string", "default": "unknown"}


def test_attribute_description():
    fmobj = {
        "name": "test",
        "root": {
            "name": "root",
            "attributes": {
                "attr1": {
                    "type": "string",
                    "description": "This is a string attribute",
                },
                "attr2": {
                    "type": "integer",
                    "description": "This is an integer attribute",
                },
            },
        },
    }

    fm = FeatureModel.model_validate(fmobj)
    fmembers = fm.root.members()

    attr1: AttributeValidator = fmembers["attr1"]
    attr2: AttributeValidator = fmembers["attr2"]

    assert attr1.schema["description"] == "This is a string attribute"
    assert attr2.schema["description"] == "This is an integer attribute"
