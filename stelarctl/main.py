import json
from loader import load_model
from platform_model import PlatformModel


def main():
    model = load_model("stelarctl/example_models/okeanos.yaml", PlatformModel)
    print(json.dumps(model.model_dump(), indent=2))


if __name__ == "__main__":
    main()
