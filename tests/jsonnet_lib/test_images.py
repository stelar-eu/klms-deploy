import pytest
from jsonnet import JsonnetRunner

@pytest.fixture
def J() -> JsonnetRunner:
    return JsonnetRunner(
        "foo/test.jsonnet",
        ["lib"],
        """
        local images = import "images.libsonnet";
        //local url = u.url;
        //local url_from = u.url_from;
        """,
    )


def test_image_spec(J):

    imgout = J("""
{
    test1: images.image_name("my-image"),
    test2: images.image_name({ image: "my-object-image", pullPolicy: "IfNotPresent" }),
    test3: images.pull_policy("my-image"),
    test4: images.pull_policy({ image: "my-object-image", pullPolicy: "IfNotPresent" })
}
      """)

    assert imgout == {
        "test1": "my-image",
        "test2": "my-object-image",
        "test3": "Always",
        "test4": "IfNotPresent" 
    }

