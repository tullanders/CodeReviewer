# Code Reviewer Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI tool `code-reviewer` that fetches candidate code from GitHub/Google Drive/OneDrive and returns a structured JSON review via the Claude API.

**Architecture:** Retriever pattern — abstract `BaseRetriever` with three concrete implementations. A `normalizer` module filters and classifies files. The `agent` module routes, formats code, calls Claude, and parses JSON. A `cli` entry point wires it all together with argparse.

**Tech Stack:** Python 3.11+, uv + hatchling, anthropic SDK, requests, google-api-python-client, google-auth, msal, python-dotenv, pytest

---

## File Map

| File | Ansvar |
|------|--------|
| `pyproject.toml` | Paketmetadata, entry point, beroenden |
| `code_reviewer/__init__.py` | Paketmarkör |
| `code_reviewer/retrievers/__init__.py` | Re-exporterar retrievers |
| `code_reviewer/retrievers/base.py` | `CodeFile` dataclass, `BaseRetriever` ABC |
| `code_reviewer/retrievers/github.py` | GitHub REST API |
| `code_reviewer/retrievers/gdrive.py` | Google Drive API v3 |
| `code_reviewer/retrievers/onedrive.py` | Microsoft Graph API |
| `code_reviewer/normalizer.py` | `detect_language`, `normalize`, `detect_majority_language` |
| `code_reviewer/config.py` | Env var-laddning via python-dotenv |
| `code_reviewer/agent.py` | `route`, `load_prompt`, `_format_code`, `_call_claude`, `review` |
| `code_reviewer/cli.py` | `main()` — argparse entry point |
| `code_reviewer/prompts/__init__.py` | Paketmarkör för importlib.resources |
| `code_reviewer/prompts/review_ts.md` | Granskningsprompt TypeScript |
| `code_reviewer/prompts/review_cs.md` | Granskningsprompt C# |
| `code_reviewer/prompts/review_cpp.md` | Granskningsprompt C++ |
| `.env.example` | Mall för env vars |
| `tests/__init__.py` | Testpaketmarkör |
| `tests/retrievers/__init__.py` | Testpaketmarkör |
| `tests/retrievers/test_github.py` | GitHub retriever-tester |
| `tests/retrievers/test_gdrive.py` | Google Drive retriever-tester |
| `tests/retrievers/test_onedrive.py` | OneDrive retriever-tester |
| `tests/test_normalizer.py` | Normalizer-tester |
| `tests/test_agent.py` | Agent-tester |
| `tests/test_cli.py` | CLI-tester |

---

## Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `code_reviewer/__init__.py`
- Create: `code_reviewer/retrievers/__init__.py`
- Create: `code_reviewer/prompts/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/retrievers/__init__.py`
- Create: `.env.example`

- [ ] **Step 1: Skapa `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "code-reviewer"
version = "0.1.0"
description = "Automatisk kodgranskning av rekryteringskandidater via Claude API"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.50.0",
    "requests>=2.31.0",
    "google-api-python-client>=2.100.0",
    "google-auth>=2.23.0",
    "msal>=1.24.0",
    "python-dotenv>=1.0.0",
]

[project.scripts]
code-reviewer = "code_reviewer.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["code_reviewer"]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
]
```

- [ ] **Step 2: Skapa katalogstruktur**

```bash
mkdir -p code_reviewer/retrievers code_reviewer/prompts tests/retrievers
touch code_reviewer/__init__.py
touch code_reviewer/retrievers/__init__.py
touch code_reviewer/prompts/__init__.py
touch tests/__init__.py
touch tests/retrievers/__init__.py
```

- [ ] **Step 3: Skapa `.env.example` och `.gitignore`**

```env
# .env.example
ANTHROPIC_API_KEY=sk-ant-...
GITHUB_TOKEN=ghp_...
GOOGLE_SERVICE_ACCOUNT_JSON=/path/to/service-account.json
MS_TENANT_ID=
MS_CLIENT_ID=
MS_CLIENT_SECRET=
```

```gitignore
# .gitignore
.env
output/
__pycache__/
*.pyc
.venv/
dist/
```

- [ ] **Step 4: Installera beroenden**

```bash
uv sync --dev
```

Förväntat: alla paket installeras utan fel.

- [ ] **Step 5: Commit**

```bash
git init
git add pyproject.toml .env.example code_reviewer/ tests/
git commit -m "chore: scaffold project with uv + hatchling"
```

---

## Task 2: Base types

**Files:**
- Create: `code_reviewer/retrievers/base.py`
- Create: `tests/retrievers/test_base.py`

- [ ] **Step 1: Skriv det fallande testet**

```python
# tests/retrievers/test_base.py
from code_reviewer.retrievers.base import CodeFile

def test_codefile_fields():
    f = CodeFile(path="src/index.ts", content="const x = 1;", language="typescript")
    assert f.path == "src/index.ts"
    assert f.content == "const x = 1;"
    assert f.language == "typescript"
```

- [ ] **Step 2: Kör testet och verifiera att det misslyckas**

```bash
uv run pytest tests/retrievers/test_base.py -v
```

Förväntat: `ImportError: cannot import name 'CodeFile'`

- [ ] **Step 3: Implementera `base.py`**

```python
# code_reviewer/retrievers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CodeFile:
    path: str
    content: str
    language: str


class BaseRetriever(ABC):
    @abstractmethod
    def fetch(self, url: str) -> list[CodeFile]:
        pass
```

- [ ] **Step 4: Kör testet och verifiera att det passerar**

```bash
uv run pytest tests/retrievers/test_base.py -v
```

Förväntat: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add code_reviewer/retrievers/base.py tests/retrievers/test_base.py
git commit -m "feat: add CodeFile dataclass and BaseRetriever ABC"
```

---

## Task 3: Normalizer

**Files:**
- Create: `code_reviewer/normalizer.py`
- Create: `tests/test_normalizer.py`

- [ ] **Step 1: Skriv de fallande testerna**

```python
# tests/test_normalizer.py
import pytest
from code_reviewer.retrievers.base import CodeFile
from code_reviewer.normalizer import detect_language, normalize, detect_majority_language


def test_detect_language_ts():
    assert detect_language("src/index.ts") == "typescript"

def test_detect_language_tsx():
    assert detect_language("components/Button.tsx") == "typescript"

def test_detect_language_csharp():
    assert detect_language("Models/User.cs") == "csharp"

def test_detect_language_cpp():
    assert detect_language("src/main.cpp") == "cpp"

def test_detect_language_header():
    assert detect_language("include/utils.h") == "cpp"

def test_detect_language_hpp():
    assert detect_language("include/utils.hpp") == "cpp"

def test_detect_language_python():
    assert detect_language("scripts/helper.py") == "python"

def test_detect_language_unknown():
    assert detect_language("README.md") == "unknown"


def _make(path: str, lang: str = "typescript") -> CodeFile:
    return CodeFile(path=path, content="x", language=lang)


def test_normalize_filters_node_modules():
    files = [_make("src/index.ts"), _make("node_modules/lodash/index.ts")]
    assert [f.path for f in normalize(files)] == ["src/index.ts"]

def test_normalize_filters_bin():
    files = [_make("src/index.ts"), _make("bin/Release/app.ts")]
    assert [f.path for f in normalize(files)] == ["src/index.ts"]

def test_normalize_filters_unknown_extension():
    files = [_make("src/index.ts"), CodeFile("README.md", "docs", "unknown")]
    assert len(normalize(files)) == 1

def test_normalize_sorts_tests_last():
    files = [_make("tests/test_main.ts"), _make("src/main.ts")]
    result = normalize(files)
    assert result[0].path == "src/main.ts"
    assert result[1].path == "tests/test_main.ts"

def test_normalize_sorts_spec_last():
    files = [_make("src/main.spec.ts"), _make("src/main.ts")]
    result = normalize(files)
    assert result[0].path == "src/main.ts"

def test_normalize_caps_at_max_files():
    files = [_make(f"src/file{i}.ts") for i in range(100)]
    assert len(normalize(files)) == 50


def test_detect_majority_language_returns_most_common():
    files = [
        CodeFile("a.ts", "", "typescript"),
        CodeFile("b.ts", "", "typescript"),
        CodeFile("c.cs", "", "csharp"),
    ]
    assert detect_majority_language(files) == "typescript"

def test_detect_majority_language_empty_returns_unknown():
    assert detect_majority_language([]) == "unknown"

def test_detect_majority_language_ignores_unknown():
    files = [
        CodeFile("a.ts", "", "typescript"),
        CodeFile("README.md", "", "unknown"),
    ]
    assert detect_majority_language(files) == "typescript"
```

- [ ] **Step 2: Kör testerna och verifiera att de misslyckas**

```bash
uv run pytest tests/test_normalizer.py -v
```

Förväntat: `ImportError: cannot import name 'detect_language'`

- [ ] **Step 3: Implementera `normalizer.py`**

```python
# code_reviewer/normalizer.py
from collections import Counter
from pathlib import Path

from code_reviewer.retrievers.base import CodeFile

INCLUDE_EXTENSIONS = {".ts", ".tsx", ".cs", ".cpp", ".h", ".hpp", ".py"}
EXCLUDE_DIRS = {"node_modules", "bin", "obj", ".git", "dist", "build", "__pycache__"}
MAX_FILE_SIZE_KB = 100
MAX_FILES = 50

_EXT_TO_LANG: dict[str, str] = {
    ".ts": "typescript",
    ".tsx": "typescript",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
    ".py": "python",
}


def detect_language(path: str) -> str:
    return _EXT_TO_LANG.get(Path(path).suffix, "unknown")


def _is_test_file(path: str) -> bool:
    parts = Path(path).parts
    if any(p in ("tests", "test", "__tests__", "spec") for p in parts[:-1]):
        return True
    stem = Path(path).stem
    return stem.startswith("test_") or stem.endswith((".spec", ".test"))


def _should_include(path: str) -> bool:
    parts = Path(path).parts
    if any(part in EXCLUDE_DIRS for part in parts[:-1]):
        return False
    return Path(path).suffix in INCLUDE_EXTENSIONS


def normalize(files: list[CodeFile]) -> list[CodeFile]:
    included = [f for f in files if _should_include(f.path)]
    included.sort(key=lambda f: (1 if _is_test_file(f.path) else 0, f.path))
    return included[:MAX_FILES]


def detect_majority_language(files: list[CodeFile]) -> str:
    counts = Counter(f.language for f in files if f.language != "unknown")
    if not counts:
        return "unknown"
    return counts.most_common(1)[0][0]
```

- [ ] **Step 4: Kör testerna och verifiera att de passerar**

```bash
uv run pytest tests/test_normalizer.py -v
```

Förväntat: alla tester `PASSED`

- [ ] **Step 5: Commit**

```bash
git add code_reviewer/normalizer.py tests/test_normalizer.py
git commit -m "feat: add normalizer with language detection and file filtering"
```

---

## Task 4: Config

**Files:**
- Create: `code_reviewer/config.py`

Ingen separat testfil — `config.py` är ren infrastruktur som valideras av agent-testerna.

- [ ] **Step 1: Implementera `config.py`**

```python
# code_reviewer/config.py
import os

from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
GITHUB_TOKEN: str | None = os.getenv("GITHUB_TOKEN")
GOOGLE_SERVICE_ACCOUNT_JSON: str | None = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
MS_TENANT_ID: str | None = os.getenv("MS_TENANT_ID")
MS_CLIENT_ID: str | None = os.getenv("MS_CLIENT_ID")
MS_CLIENT_SECRET: str | None = os.getenv("MS_CLIENT_SECRET")
```

- [ ] **Step 2: Commit**

```bash
git add code_reviewer/config.py
git commit -m "feat: add config module for env var loading"
```

---

## Task 5: GitHub retriever

**Files:**
- Create: `code_reviewer/retrievers/github.py`
- Create: `tests/retrievers/test_github.py`

- [ ] **Step 1: Skriv de fallande testerna**

```python
# tests/retrievers/test_github.py
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


def test_should_include_valid_ts():
    r = GitHubRetriever()
    assert r._should_include("src/index.ts", 500) is True


def test_should_include_excludes_node_modules():
    r = GitHubRetriever()
    assert r._should_include("node_modules/lodash/index.ts", 500) is False


def test_should_include_excludes_large_files():
    r = GitHubRetriever()
    assert r._should_include("src/index.ts", 200 * 1024) is False


def test_should_include_excludes_unknown_extension():
    r = GitHubRetriever()
    assert r._should_include("README.md", 100) is False


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
```

- [ ] **Step 2: Kör testerna och verifiera att de misslyckas**

```bash
uv run pytest tests/retrievers/test_github.py -v
```

Förväntat: `ImportError`

- [ ] **Step 3: Implementera `github.py`**

```python
# code_reviewer/retrievers/github.py
import re
from pathlib import Path

import requests

from code_reviewer import config
from code_reviewer.normalizer import EXCLUDE_DIRS, INCLUDE_EXTENSIONS, MAX_FILE_SIZE_KB, MAX_FILES, detect_language
from code_reviewer.retrievers.base import BaseRetriever, CodeFile

_URL_RE = re.compile(r"github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/|$)")


class GitHubRetriever(BaseRetriever):
    def _parse_url(self, url: str) -> tuple[str, str]:
        m = _URL_RE.search(url)
        if not m:
            raise ValueError(f"Kan inte parsa GitHub-URL: {url}")
        return m.group(1), m.group(2)

    def _should_include(self, path: str, size: int) -> bool:
        parts = Path(path).parts
        if any(part in EXCLUDE_DIRS for part in parts[:-1]):
            return False
        if Path(path).suffix not in INCLUDE_EXTENSIONS:
            return False
        return size <= MAX_FILE_SIZE_KB * 1024

    def fetch(self, url: str) -> list[CodeFile]:
        owner, repo = self._parse_url(url)
        headers = {"Accept": "application/vnd.github+json"}
        if config.GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {config.GITHUB_TOKEN}"

        resp = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1",
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()

        files: list[CodeFile] = []
        for item in resp.json().get("tree", []):
            if item["type"] != "blob":
                continue
            if not self._should_include(item["path"], item.get("size", 0)):
                continue
            if len(files) >= MAX_FILES:
                break

            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{item['path']}"
            content_resp = requests.get(raw_url, headers=headers, timeout=30)
            content_resp.raise_for_status()

            files.append(
                CodeFile(
                    path=item["path"],
                    content=content_resp.text,
                    language=detect_language(item["path"]),
                )
            )
        return files
```

- [ ] **Step 4: Kör testerna och verifiera att de passerar**

```bash
uv run pytest tests/retrievers/test_github.py -v
```

Förväntat: alla `PASSED`

- [ ] **Step 5: Commit**

```bash
git add code_reviewer/retrievers/github.py tests/retrievers/test_github.py
git commit -m "feat: add GitHub retriever"
```

---

## Task 6: Google Drive retriever

**Files:**
- Create: `code_reviewer/retrievers/gdrive.py`
- Create: `tests/retrievers/test_gdrive.py`

- [ ] **Step 1: Skriv de fallande testerna**

```python
# tests/retrievers/test_gdrive.py
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
```

- [ ] **Step 2: Kör testerna och verifiera att de misslyckas**

```bash
uv run pytest tests/retrievers/test_gdrive.py -v
```

Förväntat: `ImportError`

- [ ] **Step 3: Implementera `gdrive.py`**

```python
# code_reviewer/retrievers/gdrive.py
import io
import re

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account

from code_reviewer import config
from code_reviewer.normalizer import INCLUDE_EXTENSIONS, MAX_FILE_SIZE_KB, MAX_FILES, detect_language
from code_reviewer.retrievers.base import BaseRetriever, CodeFile
from pathlib import Path

_FOLDER_ID_RE = re.compile(r"folders/([a-zA-Z0-9_-]+)")
_FOLDER_MIME = "application/vnd.google-apps.folder"
_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


class GoogleDriveRetriever(BaseRetriever):
    def _parse_folder_id(self, url: str) -> str:
        m = _FOLDER_ID_RE.search(url)
        if not m:
            raise ValueError(f"Kan inte hitta folder-ID i URL: {url}")
        return m.group(1)

    def _build_service(self):
        if not config.GOOGLE_SERVICE_ACCOUNT_JSON:
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON env var saknas")
        creds = service_account.Credentials.from_service_account_file(
            config.GOOGLE_SERVICE_ACCOUNT_JSON, scopes=_SCOPES
        )
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    def _list_files(self, service, folder_id: str) -> list[dict]:
        results: list[dict] = []
        page_token = None
        while True:
            resp = service.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="nextPageToken, files(id,name,mimeType,size)",
                pageToken=page_token,
            ).execute()
            for item in resp.get("files", []):
                if item["mimeType"] == _FOLDER_MIME:
                    results.extend(self._list_files(service, item["id"]))
                else:
                    results.append(item)
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return results

    def _download(self, service, file_id: str) -> str:
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, service.files().get_media(fileId=file_id))
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue().decode("utf-8", errors="replace")

    def fetch(self, url: str) -> list[CodeFile]:
        folder_id = self._parse_folder_id(url)
        service = self._build_service()
        items = self._list_files(service, folder_id)

        files: list[CodeFile] = []
        for item in items:
            if len(files) >= MAX_FILES:
                break
            name = item["name"]
            if Path(name).suffix not in INCLUDE_EXTENSIONS:
                continue
            if int(item.get("size", 0)) > MAX_FILE_SIZE_KB * 1024:
                continue
            content = self._download(service, item["id"])
            files.append(CodeFile(path=name, content=content, language=detect_language(name)))
        return files
```

- [ ] **Step 4: Kör testerna och verifiera att de passerar**

```bash
uv run pytest tests/retrievers/test_gdrive.py -v
```

Förväntat: alla `PASSED`

- [ ] **Step 5: Commit**

```bash
git add code_reviewer/retrievers/gdrive.py tests/retrievers/test_gdrive.py
git commit -m "feat: add Google Drive retriever"
```

---

## Task 7: OneDrive retriever

**Files:**
- Create: `code_reviewer/retrievers/onedrive.py`
- Create: `tests/retrievers/test_onedrive.py`

- [ ] **Step 1: Skriv de fallande testerna**

```python
# tests/retrievers/test_onedrive.py
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
```

- [ ] **Step 2: Kör testerna och verifiera att de misslyckas**

```bash
uv run pytest tests/retrievers/test_onedrive.py -v
```

Förväntat: `ImportError`

- [ ] **Step 3: Implementera `onedrive.py`**

```python
# code_reviewer/retrievers/onedrive.py
import base64
from pathlib import Path

import msal
import requests

from code_reviewer import config
from code_reviewer.normalizer import INCLUDE_EXTENSIONS, MAX_FILE_SIZE_KB, MAX_FILES, detect_language
from code_reviewer.retrievers.base import BaseRetriever, CodeFile

_GRAPH = "https://graph.microsoft.com/v1.0"


class OneDriveRetriever(BaseRetriever):
    def _encode_share_url(self, url: str) -> str:
        encoded = base64.urlsafe_b64encode(url.encode()).rstrip(b"=").decode()
        return f"u!{encoded}"

    def _get_token(self) -> str:
        for var in ("MS_TENANT_ID", "MS_CLIENT_ID", "MS_CLIENT_SECRET"):
            if not getattr(config, var):
                raise RuntimeError(f"{var} env var saknas")
        app = msal.ConfidentialClientApplication(
            client_id=config.MS_CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{config.MS_TENANT_ID}",
            client_credential=config.MS_CLIENT_SECRET,
        )
        result = app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        if "access_token" not in result:
            raise RuntimeError(f"Token-fel: {result.get('error_description', 'okänt')}")
        return result["access_token"]

    def _list_items(self, token: str, item_url: str) -> list[dict]:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(item_url, headers=headers, timeout=30)
        resp.raise_for_status()
        items = resp.json().get("value", [])

        result: list[dict] = []
        for item in items:
            if "folder" in item:
                child_url = (
                    f"{_GRAPH}/drives/{item['parentReference']['driveId']}"
                    f"/items/{item['id']}/children"
                )
                result.extend(self._list_items(token, child_url))
            else:
                result.append(item)
        return result

    def fetch(self, url: str) -> list[CodeFile]:
        token = self._get_token()
        encoded = self._encode_share_url(url)
        share_url = f"{_GRAPH}/shares/{encoded}/driveItem/children"
        items = self._list_items(token, share_url)

        files: list[CodeFile] = []
        for item in items:
            if len(files) >= MAX_FILES:
                break
            name = item["name"]
            if Path(name).suffix not in INCLUDE_EXTENSIONS:
                continue
            if item.get("size", 0) > MAX_FILE_SIZE_KB * 1024:
                continue
            download_url = item.get("@microsoft.graph.downloadUrl")
            if not download_url:
                continue
            content_resp = requests.get(download_url, timeout=30)
            content_resp.raise_for_status()
            files.append(CodeFile(path=name, content=content_resp.text, language=detect_language(name)))
        return files
```

- [ ] **Step 4: Kör testerna och verifiera att de passerar**

```bash
uv run pytest tests/retrievers/test_onedrive.py -v
```

Förväntat: alla `PASSED`

- [ ] **Step 5: Uppdatera `retrievers/__init__.py`**

```python
# code_reviewer/retrievers/__init__.py
from .github import GitHubRetriever
from .gdrive import GoogleDriveRetriever
from .onedrive import OneDriveRetriever

__all__ = ["GitHubRetriever", "GoogleDriveRetriever", "OneDriveRetriever"]
```

- [ ] **Step 6: Commit**

```bash
git add code_reviewer/retrievers/__init__.py code_reviewer/retrievers/onedrive.py tests/retrievers/test_onedrive.py
git commit -m "feat: add OneDrive retriever and re-export all retrievers"
```

---

## Task 8: Prompts

**Files:**
- Create: `code_reviewer/prompts/review_ts.md`
- Create: `code_reviewer/prompts/review_cs.md`
- Create: `code_reviewer/prompts/review_cpp.md`

Inga automatiserade tester — promptinnehållet verifieras manuellt.

- [ ] **Step 1: Skapa `review_ts.md`**

```markdown
# Granskningsinstruktion — TypeScript

Du är en senior TypeScript-utvecklare som granskar kod från en rekryteringskandidat.
Analysera ALLA bifogade filer. Bilda en helhetsbedömning.

## Bedömningskriterier (0–4 per dimension)

- **korrekthet**: Löser koden problemet? Hanteras edge cases? Fungerar logiken?
- **läsbarhet**: Namngivning, struktur, kommentarer där de behövs
- **felhantering**: Exceptions, null-checks, robusthet mot felaktig input
- **testbarhet**: Finns tester? Är koden designad för testbarhet (dependency injection etc.)?
- **idiomatik**: Används TypeScript idiomatiskt? Undviker `any`, använder generics, strikt typing

## Poängskala
0 = saknas helt eller mycket bristfällig
1 = under förväntan
2 = godkänd nivå
3 = bra
4 = exemplarisk

## AI-indikatorer att flagga
- Ovanligt homogen kodstil över alla filer (aldrig inkonsekvent)
- Kommentarer som förklarar triviala saker
- Perfekt men opersonlig namngivning
- Lösningar som känns genererade snarare än genomtänkta

## Output-format

Svara ALLTID med giltig JSON och absolut inget annat — ingen inledande text, inga avslutande kommentarer:

{
  "dimensioner": {
    "korrekthet":   { "poäng": 0, "motivering": "..." },
    "läsbarhet":    { "poäng": 0, "motivering": "..." },
    "felhantering": { "poäng": 0, "motivering": "..." },
    "testbarhet":   { "poäng": 0, "motivering": "..." },
    "idiomatik":    { "poäng": 0, "motivering": "..." }
  },
  "totalpoäng": 0,
  "styrkor": ["..."],
  "svagheter": ["..."],
  "ai_indikationer": {
    "nivå": "låg",
    "flaggor": []
  },
  "frågor_till_live_session": ["..."]
}
```

- [ ] **Step 2: Skapa `review_cs.md`**

```markdown
# Granskningsinstruktion — C#

Du är en senior C#-utvecklare som granskar kod från en rekryteringskandidat.
Analysera ALLA bifogade filer. Bilda en helhetsbedömning.

## Bedömningskriterier (0–4 per dimension)

- **korrekthet**: Löser koden problemet? Hanteras edge cases? Fungerar logiken?
- **läsbarhet**: Namngivning (PascalCase/camelCase), struktur, XML-dokumentation där relevant
- **felhantering**: try/catch, nullable reference types, robusthet mot felaktig input
- **testbarhet**: Finns tester (xUnit/NUnit/MSTest)? SOLID-principer? Dependency injection?
- **idiomatik**: Används C# idiomatiskt? async/await, LINQ, record types, pattern matching

## Poängskala
0 = saknas helt eller mycket bristfällig
1 = under förväntan
2 = godkänd nivå
3 = bra
4 = exemplarisk

## AI-indikatorer att flagga
- Ovanligt homogen kodstil över alla filer
- Kommentarer som förklarar triviala saker
- Perfekt men opersonlig namngivning
- Lösningar som känns genererade snarare än genomtänkta

## Output-format

Svara ALLTID med giltig JSON och absolut inget annat:

{
  "dimensioner": {
    "korrekthet":   { "poäng": 0, "motivering": "..." },
    "läsbarhet":    { "poäng": 0, "motivering": "..." },
    "felhantering": { "poäng": 0, "motivering": "..." },
    "testbarhet":   { "poäng": 0, "motivering": "..." },
    "idiomatik":    { "poäng": 0, "motivering": "..." }
  },
  "totalpoäng": 0,
  "styrkor": ["..."],
  "svagheter": ["..."],
  "ai_indikationer": {
    "nivå": "låg",
    "flaggor": []
  },
  "frågor_till_live_session": ["..."]
}
```

- [ ] **Step 3: Skapa `review_cpp.md`**

```markdown
# Granskningsinstruktion — C++

Du är en senior C++-utvecklare som granskar kod från en rekryteringskandidat.
Analysera ALLA bifogade filer. Bilda en helhetsbedömning.

## Bedömningskriterier (0–4 per dimension)

- **korrekthet**: Löser koden problemet? Hanteras edge cases? Minneshantering?
- **läsbarhet**: Namngivning, struktur, header/implementation-separation
- **felhantering**: Undantag, return codes, RAII, null-pointer safety
- **testbarhet**: Finns tester (Google Test/Catch2)? Är koden testbar (minimal global state)?
- **idiomatik**: Används modern C++ (C++17/20)? Smart pointers, move semantics, const correctness, STL

## Poängskala
0 = saknas helt eller mycket bristfällig
1 = under förväntan
2 = godkänd nivå
3 = bra
4 = exemplarisk

## AI-indikatorer att flagga
- Ovanligt homogen kodstil över alla filer
- Kommentarer som förklarar triviala saker
- Perfekt men opersonlig namngivning
- Lösningar som känns genererade snarare än genomtänkta

## Output-format

Svara ALLTID med giltig JSON och absolut inget annat:

{
  "dimensioner": {
    "korrekthet":   { "poäng": 0, "motivering": "..." },
    "läsbarhet":    { "poäng": 0, "motivering": "..." },
    "felhantering": { "poäng": 0, "motivering": "..." },
    "testbarhet":   { "poäng": 0, "motivering": "..." },
    "idiomatik":    { "poäng": 0, "motivering": "..." }
  },
  "totalpoäng": 0,
  "styrkor": ["..."],
  "svagheter": ["..."],
  "ai_indikationer": {
    "nivå": "låg",
    "flaggor": []
  },
  "frågor_till_live_session": ["..."]
}
```

- [ ] **Step 4: Commit**

```bash
git add code_reviewer/prompts/
git commit -m "feat: add review prompts for TypeScript, C#, and C++"
```

---

## Task 9: Agent

**Files:**
- Create: `code_reviewer/agent.py`
- Create: `tests/test_agent.py`

- [ ] **Step 1: Skriv de fallande testerna**

```python
# tests/test_agent.py
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
```

- [ ] **Step 2: Kör testerna och verifiera att de misslyckas**

```bash
uv run pytest tests/test_agent.py -v
```

Förväntat: `ImportError`

- [ ] **Step 3: Implementera `agent.py`**

```python
# code_reviewer/agent.py
import datetime
import json
import re
from importlib.resources import files as resource_files

import anthropic

from code_reviewer import config
from code_reviewer.normalizer import detect_majority_language, normalize
from code_reviewer.retrievers.base import BaseRetriever, CodeFile
from code_reviewer.retrievers.gdrive import GoogleDriveRetriever
from code_reviewer.retrievers.github import GitHubRetriever
from code_reviewer.retrievers.onedrive import OneDriveRetriever

_PROMPT_MAP = {
    "typescript": "review_ts.md",
    "csharp": "review_cs.md",
    "cpp": "review_cpp.md",
}


def route(url: str) -> BaseRetriever:
    if "github.com" in url:
        return GitHubRetriever()
    if "drive.google.com" in url:
        return GoogleDriveRetriever()
    if "onedrive.live.com" in url or "sharepoint.com" in url:
        return OneDriveRetriever()
    raise ValueError(f"Okänd URL-typ: {url}")


def load_prompt(language: str, custom_path: str | None = None) -> str:
    if custom_path:
        with open(custom_path, encoding="utf-8") as f:
            return f.read()
    filename = _PROMPT_MAP.get(language)
    if not filename:
        raise ValueError(
            f"Inget prompt för språk '{language}'. Ange en promptfil med --prompt."
        )
    return resource_files("code_reviewer.prompts").joinpath(filename).read_text(encoding="utf-8")


def _format_code(files: list[CodeFile]) -> str:
    parts = [f"### {f.path}\n\n```{f.language}\n{f.content}\n```" for f in files]
    return "\n\n".join(parts)


def _call_claude(prompt: str, code: str) -> str:
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY env var saknas")
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": f"{prompt}\n\n---\n\n{code}"}],
    )
    return message.content[0].text


def _parse_json(text: str) -> dict:
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    raw = match.group(1) if match else text.strip()
    return json.loads(raw)


def review(
    url: str,
    kandidat_id: str | None = None,
    prompt_path: str | None = None,
) -> dict:
    retriever = route(url)
    raw_files = retriever.fetch(url)
    files = normalize(raw_files)
    language = detect_majority_language(files)

    prompt = load_prompt(language, prompt_path)
    code = _format_code(files)
    response_text = _call_claude(prompt, code)
    result = _parse_json(response_text)

    return {
        "kandidat_id": kandidat_id,
        "url": url,
        "språk": language,
        "tidsstämpel": datetime.datetime.utcnow().isoformat() + "Z",
        **result,
    }
```

- [ ] **Step 4: Kör testerna och verifiera att de passerar**

```bash
uv run pytest tests/test_agent.py -v
```

Förväntat: alla `PASSED`

- [ ] **Step 5: Commit**

```bash
git add code_reviewer/agent.py tests/test_agent.py
git commit -m "feat: add agent with routing, prompt loading, and Claude integration"
```

---

## Task 10: CLI

**Files:**
- Create: `code_reviewer/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Skriv de fallande testerna**

```python
# tests/test_cli.py
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
```

- [ ] **Step 2: Kör testerna och verifiera att de misslyckas**

```bash
uv run pytest tests/test_cli.py -v
```

Förväntat: `ImportError`

- [ ] **Step 3: Implementera `cli.py`**

```python
# code_reviewer/cli.py
import argparse
import json
import os
import sys

from code_reviewer import agent


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="code-reviewer",
        description="Automatisk kodgranskning av rekryteringskandidater via Claude API",
    )
    parser.add_argument("--url", required=True, help="GitHub/Google Drive/OneDrive URL")
    parser.add_argument("--kandidat", default=None, metavar="ID", help="Kandidat-ID i output")
    parser.add_argument("--prompt", default=None, metavar="FIL", help="Sökväg till egen promptfil (.md)")
    parser.add_argument("--output", default=None, metavar="FIL", help="Sökväg till output JSON-fil (default: stdout)")

    args = parser.parse_args()

    result = agent.review(
        url=args.url,
        kandidat_id=args.kandidat,
        prompt_path=args.prompt,
    )

    output_json = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"Rapport sparad: {args.output}", file=sys.stderr)
    else:
        print(output_json)
```

- [ ] **Step 4: Kör testerna och verifiera att de passerar**

```bash
uv run pytest tests/test_cli.py -v
```

Förväntat: alla `PASSED`

- [ ] **Step 5: Kör hela testsviten**

```bash
uv run pytest tests/ -v
```

Förväntat: alla tester `PASSED`

- [ ] **Step 6: Verifiera att CLI-kommandot fungerar lokalt**

Sätt `ANTHROPIC_API_KEY` i en `.env`-fil. Kör sedan:

```bash
uv run code-reviewer --help
```

Förväntat: argparse-hjälptext visas utan fel.

- [ ] **Step 7: Commit**

```bash
git add code_reviewer/cli.py tests/test_cli.py
git commit -m "feat: add CLI entry point"
```

---

## Task 11: Installationsverifiering

- [ ] **Step 1: Bygg och installera som uv-verktyg**

```bash
uv tool install .
```

Förväntat: `Installed 1 package in ...ms`

- [ ] **Step 2: Verifiera att kommandot är tillgängligt**

```bash
code-reviewer --help
```

Förväntat: hjälptext med `--url`, `--kandidat`, `--prompt`, `--output`

- [ ] **Step 3: Commit**

```bash
git add .
git commit -m "chore: verify installable CLI works end-to-end"
```
