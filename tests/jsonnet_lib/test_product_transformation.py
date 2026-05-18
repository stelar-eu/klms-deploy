import pytest
from jsonnet import JsonnetRunner


@pytest.fixture
def J() -> JsonnetRunner:
    return JsonnetRunner(
        "tests/jsonnet_lib/test_product_transformation.jsonnet",
        ["."],
        """
        local product_transformation = import "lib/util/product_transformation.libsonnet";
        """,
    )


def test_extract_components_from_wrapped_fullspec(J: JsonnetRunner):
    out = J(
        """
        local fullspec = {
          klms: {
            core_components: ["api", "postgres", "redis"],
            optional_components: ["llm_search", "sde", "previewer"],
            cluster: ["cert_manager", "grafana"],
            sde: {
              components: ["kafka", "kafbat", "zookeeper", "flink", "sdemanager"],
            },
          },
        };

        product_transformation.extract_components(fullspec)
        """
    )

    assert out == {
        "api": {},
        "postgres": {},
        "redis": {},
        "llm_search": {},
        "sde": {},
        "previewer": {},
        "cert_manager": {},
        "grafana": {},
    }


def test_extract_components_from_bare_root_fullspec(J: JsonnetRunner):
    out = J(
        """
        local fullspec = {
          core_components: ["ckan", "solr"],
          optional_components: ["visualizer", "airflow"],
          cluster: ["prometheus"],
        };

        product_transformation.extract_components(fullspec)
        """
    )

    assert out == {
        "ckan": {},
        "solr": {},
        "visualizer": {},
        "airflow": {},
        "prometheus": {},
    }


def test_extract_configuration_returns_unwrapped_root(J: JsonnetRunner):
    out = J(
        """
        local fullspec = {
          klms: {
            core_components: ["redis", "ckan"],
            optional_components: ["previewer"],
            cluster: [],

            redis: {
              PORT: 6379,
              IMAGE: "redis:7",
              REDIS_HOST: "redis",
            },

            ckan: {
              CKAN_ADMIN_PASSWORD: "secret",
              PORT: 5000,
              IMAGE: "petroud/stelar-tuc:ckan",
            },

            previewer: {
              PORT: 8080,
              IMAGE: "petroud/stelar-previewer:latest",
              CONTEXT_PATH: "previewer",
            },

            api: {
              PORT: 80,
              IMAGE: "petroud/stelar-api:prod",
            },
          },
        };

        product_transformation.extract_configuration(fullspec)
        """
    )

    assert out == {
        "core_components": ["redis", "ckan"],
        "optional_components": ["previewer"],
        "cluster": [],
        "redis": {
            "PORT": 6379,
            "IMAGE": "redis:7",
            "REDIS_HOST": "redis",
        },
        "ckan": {
            "CKAN_ADMIN_PASSWORD": "secret",
            "PORT": 5000,
            "IMAGE": "petroud/stelar-tuc:ckan",
        },
        "previewer": {
            "PORT": 8080,
            "IMAGE": "petroud/stelar-previewer:latest",
            "CONTEXT_PATH": "previewer",
        },
        "api": {
            "PORT": 80,
            "IMAGE": "petroud/stelar-api:prod",
        },
    }


def test_extract_configuration_handles_bare_root_fullspec(J: JsonnetRunner):
    out = J(
        """
        local fullspec = {
          core_components: ["api"],
          optional_components: ["llm_search"],
          cluster: ["prometheus"],

          api: {
            SMTP_SERVER: "mail.example.org",
            SMTP_PORT: "465",
            IMAGE: "petroud/stelar-api:prod",
            PORT: 80,
          },

          llm_search: {
            GROQ_API_URL: "https://api.groq.com/openai/v1",
            GROQ_MODEL: "llama",
            GROQ_API_KEY: "token",
            PORT: 8000,
            IMAGE: "petroud/semantic-dataset-search:latest",
          },

          prometheus: {},
          redis: {
            PORT: 6379,
          },
        };

        product_transformation.extract_configuration(fullspec)
        """
    )

    assert out == {
        "core_components": ["api"],
        "optional_components": ["llm_search"],
        "cluster": ["prometheus"],
        "api": {
            "SMTP_SERVER": "mail.example.org",
            "SMTP_PORT": "465",
            "IMAGE": "petroud/stelar-api:prod",
            "PORT": 80,
        },
        "llm_search": {
            "GROQ_API_URL": "https://api.groq.com/openai/v1",
            "GROQ_MODEL": "llama",
            "GROQ_API_KEY": "token",
            "PORT": 8000,
            "IMAGE": "petroud/semantic-dataset-search:latest",
        },
        "prometheus": {},
        "redis": {
            "PORT": 6379,
        },
    }
