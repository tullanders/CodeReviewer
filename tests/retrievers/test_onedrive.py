import pytest
from unittest.mock import MagicMock, patch

from code_reviewer.retrievers.onedrive import OneDriveRetriever


def test_encode_share_url_starts_with_u():
    r = OneDriveRetriever()
    encoded = r._encode_share_url("https://onedrive.live.com/share")
    assert encoded.startswith("u!")


def test_encode_share_url_no_padding():
    r = OneDriveRetriever()
    encoded = r._encode_share_url("https://example.com")
    assert "=" not in encoded


def test_fetch_filters_by_extension():
    r = OneDriveRetriever()

    items_resp = MagicMock()
    items_resp.raise_for_status = MagicMock()
    items_resp.json.return_value = {
        "value": [
            {"name": "Program.cs", "size": 500, "@microsoft.graph.downloadUrl": "http://dl/cs"},
            {"name": "readme.txt", "size": 100, "@microsoft.graph.downloadUrl": "http://dl/txt"},
        ]
    }

    content_resp = MagicMock()
    content_resp.raise_for_status = MagicMock()
    content_resp.text = "using System;"

    with patch.object(r, "_get_token", return_value="fake_token"):
        with patch("requests.get", side_effect=[items_resp, content_resp]):
            files = r.fetch("https://onedrive.live.com/?id=XYZ&cid=ABC")

    assert len(files) == 1
    assert files[0].path == "Program.cs"
    assert files[0].language == "csharp"


def test_fetch_skips_large_files():
    r = OneDriveRetriever()

    items_resp = MagicMock()
    items_resp.raise_for_status = MagicMock()
    items_resp.json.return_value = {
        "value": [
            {"name": "big.cs", "size": 200 * 1024, "@microsoft.graph.downloadUrl": "http://dl/big"},
            {"name": "small.cs", "size": 100, "@microsoft.graph.downloadUrl": "http://dl/small"},
        ]
    }

    content_resp = MagicMock()
    content_resp.raise_for_status = MagicMock()
    content_resp.text = "class X {}"

    with patch.object(r, "_get_token", return_value="fake_token"):
        with patch("requests.get", side_effect=[items_resp, content_resp]):
            files = r.fetch("https://onedrive.live.com/?id=XYZ")

    assert len(files) == 1
    assert files[0].path == "small.cs"
