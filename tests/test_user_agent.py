import requests

from cwltool.main import append_word_to_default_user_agent, main


def get_user_agent() -> str:
    return requests.utils.default_headers()["User-Agent"]


def test_cwltool_in_user_agent() -> None:
    """python-requests HTTP User-Agent should include the string 'cwltool'."""
    try:
        assert main(["--version"]) == 0
    except SystemExit as err:
        assert err.code == 0
    assert "cwltool" in get_user_agent()


def test_append_word_to_default_user_agent() -> None:
    """Confirm that append_word_to_default_user_agent works."""
    word_to_append = "foobar123"
    assert word_to_append not in get_user_agent()
    append_word_to_default_user_agent(word_to_append)
    assert word_to_append in get_user_agent()
