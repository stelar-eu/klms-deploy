import pytest
from jsonnet import JsonnetRunner


@pytest.fixture
def J() -> JsonnetRunner:
    return JsonnetRunner(
        "foo/test.jsonnet",
        ["lib"],
        """local u = import "urllib.libsonnet";
                           local url=u.url;
                        """,
    )


def test_urllib(J):

    assert J("""url(netloc="foobar")""") == "http://foobar"

    assert J("""url(scheme='https', host="foo", path="/") """) == "https://foo/"

    assert (
        J("""url(scheme='http', host="foo", port=10, path="/a") """)
        == "http://foo:10/a"
    )


def test_urllib_user_pass(J):

    assert J("""url(netloc="foobar", user='vsam')""") == "http://vsam@foobar"

    assert (
        J("""url(scheme='https', host="foo", path="/", user='vsam') """)
        == "https://vsam@foo/"
    )

    assert (
        J("""url(scheme='http', host="foo", port=10, path="/a", user="vsam") """)
        == "http://vsam@foo:10/a"
    )

    assert (
        J("""url(netloc="foobar", user='vsam', password='secret')""")
        == "http://vsam:secret@foobar"
    )

    assert (
        J(
            """url(scheme='https', host="foo", path="/", user='vsam', password='secret') """
        )
        == "https://vsam:secret@foo/"
    )

    assert (
        J(
            """url(scheme='http', host="foo", port=10, path="/a", user="vsam", password='12312') """
        )
        == "http://vsam:12312@foo:10/a"
    )


def test_urllib_errors(J):

    with pytest.raises(RuntimeError):
        J(""" url() """)

    with pytest.raises(RuntimeError):
        J(""" url(port=20) """)

    with pytest.raises(RuntimeError):
        J(""" url(port = [1,2]) """)

    with pytest.raises(RuntimeError):
        J(""" url(netloc=[1,2]) """)

    with pytest.raises(RuntimeError):
        J(""" url(netloc="f1", host="f2") """)

    with pytest.raises(RuntimeError):
        J(""" url(netloc="aaa", port=22) """)

    with pytest.raises(RuntimeError):
        J(""" url(netloc="foo", password="aaa") """)
