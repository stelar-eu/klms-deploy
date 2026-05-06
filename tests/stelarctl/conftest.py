import pytest

from typing import Any
from stelar.deploy.models.feature import FeatureModel
from pydantic import JsonValue

# The following is adapted from:
#
# Benavides, David, Pablo Trinidad, and Antonio Ruiz-Cortés.
# “Automated Reasoning on Feature Models.” In Advanced Information Systems Engineering, edited by Oscar Pastor and João Falcão e Cunha.
# Springer, 2005. https://doi.org/10.1007/11431855_34.
#
# `HIS` refers to a Home Information System, which is a system that provides
# various services to the residents of a home.

HIS_model = """
name: HIS
root:
  name: his
  attributes:
    system_name:
        type: string
    manufacturer:
        type: string
        default: "unknown"
  subfeatures:
  - rel: mandatory
    members:
    - name: supervision
      subfeatures:
        - rel: optional
          members:
          - name: flood
        - rel: mandatory
          members:
          - name: fire
          - name: intrusion
    - name: control
      subfeatures:
        - rel: mandatory
          members:
          - name: lighting
          - name: temperature
        - rel: optional
          default: []
          members:
          - name: appliances
  - rel: optional
    members:
    - name: services
      subfeatures:
      - rel: or
        members:
        - name: video_on_demand
        - name: internet_access
          subfeatures:
          - rel: alternative
            default: [wifi]
            members:
            - name: powerline
            - name: wifi
            - name: ADSL
"""


@pytest.fixture
def his_model_txt() -> str:
    return HIS_model


@pytest.fixture
def his_model_dict() -> JsonValue:
    import yaml

    return yaml.safe_load(HIS_model)


@pytest.fixture
def his_model() -> FeatureModel:
    import yaml

    return FeatureModel.model_validate(yaml.safe_load(HIS_model))
