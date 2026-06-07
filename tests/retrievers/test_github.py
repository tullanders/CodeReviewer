import pytest
from unittest.mock import MagicMock, patch

from code_reviewer.retrievers.github import GitHubRetriever


def test_parse_url_simple():
    r = GitHubRetriever()
    assert r._parse_url("https://github.com/user/repo") == ("user", "repo")


def test_parse_url_trailing_slash():
    r = GitHubRetriever()
    assert r._parse_url("https://github.com/user/repo/") == ("user", "repo")


def test_parse_url_invalid_raises():
    r = GitHubRetriever()
    with pytest.raises(ValueError, match="Kan inte parsa"):
        r._parse_url("https://notgithub.com/user/repo")


def test_fetch_returns_included_files():
    r = GitHubRetriever()

    tree_resp = MagicMock()
    tree_resp.raise_for_status = MagicMock()
    tree_resp.json.return_value = {
        "tree": [
            {"path": "src/index.ts", "type": "blob", "size": 500},
            {"path": "node_modules/x/y.ts", "type": "blob", "size": 100},
            {"path": "README.md", "type": "blob", "size": 50},
        ]
    }

    content_resp = MagicMock()
    content_resp.raise_for_status = MagicMock()
    content_resp.text = "const x = 1;"

    with patch("requests.get", side_effect=[tree_resp, content_resp]):
        files = r.fetch("https://github.com/user/repo")

    assert len(files) == 1
    assert files[0].path == "src/index.ts"
    assert files[0].content == "const x = 1;"
    assert files[0].language == "typescript"
