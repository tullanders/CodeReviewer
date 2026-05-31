import json
import sys
from unittest.mock import patch

import pytest

from code_reviewer.cli import main

_MOCK_RESULT = {
    "kandidat_id": "abc123",
    "url": "https://github.com/user/repo",
    "språk": "typescript",
    "tidsstämpel": "2026-05-31T10:00:00Z",
    "dimensioner": {
        "korrekthet": {"poäng": 3, "motivering": "ok"},
    },
    "totalpoäng": 3,
    "styrkor": [],
    "svagheter": [],
    "ai_indikationer": {"nivå": "låg", "flaggor": []},
    "frågor_till_live_session": [],
}


def test_cli_prints_json_to_stdout(capsys):
    with patch("sys.argv", ["code-reviewer", "--url", "https://github.com/user/repo", "--kandidat", "abc123"]):
        with patch("code_reviewer.agent.review", return_value=_MOCK_RESULT):
            main()
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["kandidat_id"] == "abc123"
    assert data["språk"] == "typescript"


def test_cli_writes_json_to_file(tmp_path):
    output_file = str(tmp_path / "report.json")
    with patch("sys.argv", ["code-reviewer", "--url", "https://github.com/user/repo", "--output", output_file]):
        with patch("code_reviewer.agent.review", return_value=_MOCK_RESULT):
            main()
    with open(output_file) as f:
        data = json.load(f)
    assert data["totalpoäng"] == 3


def test_cli_passes_prompt_path(capsys):
    with patch("sys.argv", [
        "code-reviewer",
        "--url", "https://github.com/user/repo",
        "--prompt", "custom.md",
    ]):
        with patch("code_reviewer.agent.review", return_value=_MOCK_RESULT) as mock_review:
            main()
    mock_review.assert_called_once_with(
        url="https://github.com/user/repo",
        kandidat_id=None,
        prompt_path="custom.md",
    )


def test_cli_missing_url_exits(capsys):
    with patch("sys.argv", ["code-reviewer"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code != 0
