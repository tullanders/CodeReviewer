import pytest
from unittest.mock import MagicMock, patch

from code_reviewer.retrievers.gdrive import GoogleDriveRetriever


def test_parse_folder_id():
    r = GoogleDriveRetriever()
    fid = r._parse_folder_id("https://drive.google.com/drive/folders/1BxiMVs0XRA5nFMdKvBd")
    assert fid == "1BxiMVs0XRA5nFMdKvBd"


def test_parse_folder_id_invalid_raises():
    r = GoogleDriveRetriever()
    with pytest.raises(ValueError, match="Kan inte hitta folder-ID"):
        r._parse_folder_id("https://drive.google.com/file/d/xyz/view")


def test_fetch_filters_by_extension():
    r = GoogleDriveRetriever()
    mock_service = MagicMock()
    mock_service.files().list().execute.return_value = {
        "files": [
            {"id": "1", "name": "index.ts", "mimeType": "text/plain", "size": "200"},
            {"id": "2", "name": "README.md", "mimeType": "text/plain", "size": "100"},
        ]
    }

    with patch.object(r, "_build_service", return_value=mock_service):
        with patch.object(r, "_download", return_value="const x = 1;"):
            files = r.fetch("https://drive.google.com/drive/folders/test_folder_id")

    assert len(files) == 1
    assert files[0].path == "index.ts"
    assert files[0].language == "typescript"
    assert files[0].content == "const x = 1;"


def test_fetch_skips_large_files():
    r = GoogleDriveRetriever()
    mock_service = MagicMock()
    mock_service.files().list().execute.return_value = {
        "files": [
            {"id": "1", "name": "big.ts", "mimeType": "text/plain", "size": str(200 * 1024)},
            {"id": "2", "name": "small.ts", "mimeType": "text/plain", "size": "100"},
        ]
    }

    with patch.object(r, "_build_service", return_value=mock_service):
        with patch.object(r, "_download", return_value="const x = 1;"):
            files = r.fetch("https://drive.google.com/drive/folders/test_id")

    assert len(files) == 1
    assert files[0].path == "small.ts"
