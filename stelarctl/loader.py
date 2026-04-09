import yaml
from pydantic import BaseModel, ValidationError
from typing import Type, TypeVar

M = TypeVar("M", bound=BaseModel)


def load_model(path: str, model_class: Type[M]) -> M:
    with open(path) as f:
        raw = yaml.safe_load(f)

    try:
        return model_class(**raw)
    except ValidationError as e:
        print(e)
        raise SystemExit(1)
