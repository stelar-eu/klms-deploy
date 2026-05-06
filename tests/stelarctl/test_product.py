from stelar.deploy.models.product import Product, ProductValidator
from stelar.deploy.models.feature import FeatureModel


def test_product(his_model: FeatureModel):
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

    print(fspec)
