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


def test_build_service_raises_when_credentials_missing(monkeypatch):
    import code_reviewer.config as cfg
    monkeypatch.setattr(cfg, "GOOGLE_SERVICE_ACCOUNT_JSON", None)
    r = GoogleDriveRetriever()
    with pytest.raises(RuntimeError, match="GOOGLE_SERVICE_ACCOUNT_JSON"):
        r._build_service()


def test_list_files_recursive():
    r = GoogleDriveRetriever()
    subfolder_id = "subfolder_id"

    # Root call returns one subfolder and one file
    root_response = {
        "files": [
            {"id": subfolder_id, "name": "src", "mimeType": "application/vnd.google-apps.folder", "size": "0"},
            {"id": "file1", "name": "root.ts", "mimeType": "text/plain", "size": "100"},
        ]
    }
    # Subfolder call returns one file
    sub_response = {
        "files": [
            {"id": "file2", "name": "nested.ts", "mimeType": "text/plain", "size": "200"},
        ]
    }

    call_count = 0

    mock_service = MagicMock()

    def execute_side_effect():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return root_response
        return sub_response

    mock_service.files().list().execute.side_effect = execute_side_effect

    result = r._list_files(mock_service, "root_id")
    assert len(result) == 2
    assert any(f["name"] == "root.ts" for f in result)
    assert any(f["name"] == "nested.ts" for f in result)


def test_list_files_skips_google_workspace_files():
    r = GoogleDriveRetriever()
    mock_service = MagicMock()
    mock_service.files().list().execute.return_value = {
        "files": [
            {"id": "1", "name": "doc", "mimeType": "application/vnd.google-apps.document", "size": "0"},
            {"id": "2", "name": "index.ts", "mimeType": "text/plain", "size": "100"},
        ]
    }

    result = r._list_files(mock_service, "folder_id")
    assert len(result) == 1
    assert result[0]["name"] == "index.ts"


def test_list_files_pagination():
    r = GoogleDriveRetriever()
    mock_service = MagicMock()

    page1 = {
        "nextPageToken": "token123",
        "files": [{"id": "1", "name": "a.ts", "mimeType": "text/plain", "size": "100"}],
    }
    page2 = {
        "files": [{"id": "2", "name": "b.ts", "mimeType": "text/plain", "size": "100"}],
    }

    mock_service.files().list().execute.side_effect = [page1, page2]

    result = r._list_files(mock_service, "folder_id")
    assert len(result) == 2
    assert result[0]["name"] == "a.ts"
    assert result[1]["name"] == "b.ts"
