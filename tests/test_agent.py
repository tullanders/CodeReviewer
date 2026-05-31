import pytest
from unittest.mock import MagicMock, patch

from code_reviewer.agent import _format_code, _parse_json, load_prompt, review, route
from code_reviewer.retrievers.base import CodeFile
from code_reviewer.retrievers.github import GitHubRetriever
from code_reviewer.retrievers.gdrive import GoogleDriveRetriever
from code_reviewer.retrievers.onedrive import OneDriveRetriever


def test_route_github():
    assert isinstance(route("https://github.com/user/repo"), GitHubRetriever)


def test_route_gdrive():
    assert isinstance(route("https://drive.google.com/drive/folders/xyz"), GoogleDriveRetriever)


def test_route_onedrive():
    assert isinstance(route("https://onedrive.live.com/?id=xyz"), OneDriveRetriever)


def test_route_sharepoint():
    assert isinstance(route("https://myorg.sharepoint.com/sites/xyz"), OneDriveRetriever)


def test_route_unknown_raises():
    with pytest.raises(ValueError, match="Okänd URL-typ"):
        route("https://dropbox.com/sh/xyz")


def test_format_code():
    files = [CodeFile(path="src/index.ts", content="const x = 1;", language="typescript")]
    result = _format_code(files)
    assert "### src/index.ts" in result
    assert "```typescript" in result
    assert "const x = 1;" in result


def test_parse_json_plain():
    assert _parse_json('{"key": "val"}') == {"key": "val"}


def test_parse_json_in_code_block():
    raw = '```json\n{"key": "val"}\n```'
    assert _parse_json(raw) == {"key": "val"}


def test_load_prompt_custom_path(tmp_path):
    p = tmp_path / "custom.md"
    p.write_text("custom prompt content")
    result = load_prompt("typescript", custom_path=str(p))
    assert result == "custom prompt content"


def test_load_prompt_bundled_typescript():
    result = load_prompt("typescript")
    assert "TypeScript" in result


def test_load_prompt_unknown_raises():
    with pytest.raises(ValueError, match="Inget prompt"):
        load_prompt("cobol")


def test_review_returns_full_report():
    mock_files = [CodeFile(path="src/main.ts", content="const x = 1;", language="typescript")]
    claude_json = (
        '{"dimensioner": {"korrekthet": {"poäng": 3, "motivering": "ok"},'
        '"läsbarhet": {"poäng": 3, "motivering": "ok"},'
        '"felhantering": {"poäng": 2, "motivering": "ok"},'
        '"testbarhet": {"poäng": 2, "motivering": "ok"},'
        '"idiomatik": {"poäng": 3, "motivering": "ok"}},'
        '"totalpoäng": 13, "styrkor": [], "svagheter": [],'
        '"ai_indikationer": {"nivå": "låg", "flaggor": []},'
        '"frågor_till_live_session": []}'
    )

    with patch("code_reviewer.agent.route") as mock_route:
        mock_retriever = MagicMock()
        mock_retriever.fetch.return_value = mock_files
        mock_route.return_value = mock_retriever
        with patch("code_reviewer.agent._call_claude", return_value=claude_json):
            with patch("code_reviewer.agent.load_prompt", return_value="you are a reviewer"):
                result = review("https://github.com/user/repo", kandidat_id="test123")

    assert result["kandidat_id"] == "test123"
    assert result["språk"] == "typescript"
    assert "tidsstämpel" in result
    assert result["totalpoäng"] == 13
