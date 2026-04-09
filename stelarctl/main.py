from loader import load_model
from platform_model import PlatformModel
from generator import generate_main_jsonnet, write_main_jsonnet


def main():
    model = load_model("stelarctl/example_models/okeanos_minimal.yaml", PlatformModel)
    write_main_jsonnet(model, ".")


if __name__ == "__main__":
    main()
