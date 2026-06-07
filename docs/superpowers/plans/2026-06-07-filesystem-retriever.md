# Filesystem Retriever Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `FilesystemRetriever` that lets `code-reviewer --url file:///abs/path/to/repo` review code that lives in a local directory, routed without colliding with the existing GitHub/Google Drive/OneDrive URL patterns.

**Architecture:** A new `FilesystemRetriever(BaseRetriever)` in `code_reviewer/retrievers/filesystem.py` parses a strict `file:///abs/path` URL, walks the directory with `os.walk` (pruning `EXCLUDE_DIRS` early), and reuses the same filtering rules as the other retrievers. Those filtering rules (`EXCLUDE_DIRS` + `INCLUDE_EXTENSIONS` + `MAX_FILE_SIZE_KB`) currently live as a private method on `GitHubRetriever`; we extract them into a shared `should_include(path, size)` in `normalizer.py` first, so the new retriever doesn't become a third copy of the same logic.

**Tech Stack:** Python 3.11+, pytest (with `tmp_path` fixture for filesystem tests), `pathlib`/`os.walk` for directory traversal — no new dependencies.

**Spec:** `docs/superpowers/specs/2026-06-07-filesystem-retriever-design.md`

---

### Task 1: Extract shared `should_include` filtering into `normalizer.py`

**Files:**
- Modify: `code_reviewer/normalizer.py`
- Modify: `code_reviewer/retrievers/github.py`
- Test: `tests/test_normalizer.py`
- Test: `tests/retrievers/test_github.py`

- [ ] **Step 1: Write failing tests for the shared `should_include` function**

Add to the top of `tests/test_normalizer.py`, extending the existing import line at line 3:

```python
from code_reviewer.normalizer import detect_language, normalize, detect_majority_language, should_include
```

Then add these tests anywhere in the file (e.g. right after the `detect_language` tests, before `_make`):

```python
def test_should_include_valid_ts():
    assert should_include("src/index.ts", 500) is True

def test_should_include_excludes_node_modules():
    assert should_include("node_modules/lodash/index.ts", 500) is False

def test_should_include_excludes_large_files():
    assert should_include("src/index.ts", 200 * 1024) is False

def test_should_include_excludes_unknown_extension():
    assert should_include("README.md", 100) is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_normalizer.py -v -k should_include`
Expected: FAIL with `ImportError: cannot import name 'should_include'`

- [ ] **Step 3: Implement `should_include` in `normalizer.py`**

Add this function right after `_should_include` (after line 44, before `def normalize`):

```python
def should_include(path: str, size: int) -> bool:
    return _should_include(path) and size <= MAX_FILE_SIZE_KB * 1024
```

This composes the existing `_should_include(path)` (dir + extension filtering, used internally by `normalize()`) with the size check that retrievers need before downloading/reading file content — avoiding a second copy of the dir+extension logic.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_normalizer.py -v -k should_include`
Expected: 4 passed

- [ ] **Step 5: Update `github.py` to use the shared `should_include`**

In `code_reviewer/retrievers/github.py`, replace the import block (lines 1-8):

```python
import re
from pathlib import Path

import requests

from code_reviewer import config
from code_reviewer.normalizer import EXCLUDE_DIRS, INCLUDE_EXTENSIONS, MAX_FILE_SIZE_KB, MAX_FILES, detect_language
from code_reviewer.retrievers.base import BaseRetriever, CodeFile
```

with:

```python
import re

import requests

from code_reviewer import config
from code_reviewer.normalizer import MAX_FILES, detect_language, should_include
from code_reviewer.retrievers.base import BaseRetriever, CodeFile
```

(`Path`, `EXCLUDE_DIRS`, `INCLUDE_EXTENSIONS`, and `MAX_FILE_SIZE_KB` were only used inside `_should_include`, which is being removed.)

Then remove the `_should_include` method entirely (lines 20-26):

```python
    def _should_include(self, path: str, size: int) -> bool:
        parts = Path(path).parts
        if any(part in EXCLUDE_DIRS for part in parts[:-1]):
            return False
        if Path(path).suffix not in INCLUDE_EXTENSIONS:
            return False
        return size <= MAX_FILE_SIZE_KB * 1024

```

Finally, in `fetch`, change the call site (currently line 45):

```python
            if not self._should_include(item["path"], item.get("size", 0)):
```

to:

```python
            if not should_include(item["path"], item.get("size", 0)):
```

- [ ] **Step 6: Move the now-obsolete `GitHubRetriever._should_include` tests to `test_normalizer.py`**

The method no longer exists on `GitHubRetriever`, so remove these four tests from `tests/retrievers/test_github.py` (lines 23-40):

```python
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


```

(They're already replaced by the equivalent free-function tests added to `test_normalizer.py` in Step 1.)

- [ ] **Step 7: Run the full normalizer + github test suites to verify everything still passes**

Run: `.venv/bin/python -m pytest tests/test_normalizer.py tests/retrievers/test_github.py -v`
Expected: all tests pass (no `should_include` references to `GitHubRetriever` remain, shared function covered in `test_normalizer.py`)

- [ ] **Step 8: Commit**

```bash
git add code_reviewer/normalizer.py code_reviewer/retrievers/github.py tests/test_normalizer.py tests/retrievers/test_github.py
git commit -m "refactor: extract shared should_include filtering into normalizer"
```

---

### Task 2: Build `FilesystemRetriever`

**Files:**
- Create: `code_reviewer/retrievers/filesystem.py`
- Test: `tests/retrievers/test_filesystem.py`

- [ ] **Step 1: Write failing tests for `_parse_url`**

Create `tests/retrievers/test_filesystem.py`:

```python
import pytest

from code_reviewer.retrievers.filesystem import FilesystemRetriever


def test_parse_url_valid_absolute_path(tmp_path):
    r = FilesystemRetriever()
    assert r._parse_url(f"file://{tmp_path}") == tmp_path


def test_parse_url_relative_path_raises():
    r = FilesystemRetriever()
    with pytest.raises(ValueError, match="absolut sökväg"):
        r._parse_url("file://relative/path")


def test_parse_url_missing_path_raises(tmp_path):
    r = FilesystemRetriever()
    missing = tmp_path / "does-not-exist"
    with pytest.raises(ValueError, match="finns inte eller är ingen katalog"):
        r._parse_url(f"file://{missing}")


def test_parse_url_file_not_directory_raises(tmp_path):
    r = FilesystemRetriever()
    file_path = tmp_path / "single_file.ts"
    file_path.write_text("const x = 1;")
    with pytest.raises(ValueError, match="finns inte eller är ingen katalog"):
        r._parse_url(f"file://{file_path}")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/retrievers/test_filesystem.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'code_reviewer.retrievers.filesystem'`

- [ ] **Step 3: Create `FilesystemRetriever` with `_parse_url` and `fetch`**

Create `code_reviewer/retrievers/filesystem.py`:

```python
import os
from pathlib import Path

from code_reviewer.normalizer import EXCLUDE_DIRS, MAX_FILES, detect_language, should_include
from code_reviewer.retrievers.base import BaseRetriever, CodeFile


class FilesystemRetriever(BaseRetriever):
    def _parse_url(self, url: str) -> Path:
        raw = url.removeprefix("file://")
        path = Path(raw)
        if not path.is_absolute():
            raise ValueError(
                f"file:// måste peka på en absolut sökväg, t.ex. file:///Users/.../repo: {url}"
            )
        if not path.is_dir():
            raise ValueError(f"Sökvägen finns inte eller är ingen katalog: {path}")
        return path

    def fetch(self, url: str) -> list[CodeFile]:
        root = self._parse_url(url)

        files: list[CodeFile] = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            for name in filenames:
                if len(files) >= MAX_FILES:
                    return files

                full_path = Path(dirpath) / name
                rel_path = full_path.relative_to(root).as_posix()
                size = full_path.stat().st_size
                if not should_include(rel_path, size):
                    continue

                try:
                    content = full_path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue

                files.append(
                    CodeFile(
                        path=rel_path,
                        content=content,
                        language=detect_language(rel_path),
                    )
                )
        return files
```

- [ ] **Step 4: Run the `_parse_url` tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/retrievers/test_filesystem.py -v -k parse_url`
Expected: 4 passed

- [ ] **Step 5: Write failing tests for `fetch`**

Append to `tests/retrievers/test_filesystem.py`:

```python
def _make_repo(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.ts").write_text("const x = 1;")
    (tmp_path / "src" / "big.ts").write_text("x" * (200 * 1024))
    (tmp_path / "README.md").write_text("# docs")
    (tmp_path / "node_modules" / "lodash").mkdir(parents=True)
    (tmp_path / "node_modules" / "lodash" / "index.ts").write_text("module.exports = {};")
    return tmp_path


def test_fetch_returns_included_files_relative_to_root(tmp_path):
    _make_repo(tmp_path)
    r = FilesystemRetriever()

    files = r.fetch(f"file://{tmp_path}")

    paths = {f.path for f in files}
    assert "src/index.ts" in paths
    assert "node_modules/lodash/index.ts" not in paths  # excluded dir, never descended into
    assert "README.md" not in paths  # unknown extension
    assert "src/big.ts" not in paths  # exceeds MAX_FILE_SIZE_KB


def test_fetch_sets_content_and_language(tmp_path):
    _make_repo(tmp_path)
    r = FilesystemRetriever()

    files = r.fetch(f"file://{tmp_path}")
    by_path = {f.path: f for f in files}

    assert by_path["src/index.ts"].content == "const x = 1;"
    assert by_path["src/index.ts"].language == "typescript"


def test_fetch_skips_unreadable_files(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ok.ts").write_text("const x = 1;")
    (tmp_path / "src" / "bad.ts").write_bytes(b"\xff\xfe\x00\x01")  # invalid UTF-8
    r = FilesystemRetriever()

    files = r.fetch(f"file://{tmp_path}")

    paths = {f.path for f in files}
    assert "src/ok.ts" in paths
    assert "src/bad.ts" not in paths


def test_fetch_respects_max_files(tmp_path):
    (tmp_path / "src").mkdir()
    for i in range(60):
        (tmp_path / "src" / f"file{i}.ts").write_text("const x = 1;")
    r = FilesystemRetriever()

    files = r.fetch(f"file://{tmp_path}")

    assert len(files) == 50
```

- [ ] **Step 6: Run the `fetch` tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/retrievers/test_filesystem.py -v -k fetch`
Expected: 4 passed

(The implementation was written together with `_parse_url` in Step 3 since `fetch` is required to instantiate a concrete `BaseRetriever` subclass — these tests exercise it directly against real `tmp_path` directories rather than mocks, since there's no HTTP layer to mock for a local retriever.)

- [ ] **Step 7: Run the entire file to make sure nothing is broken**

Run: `.venv/bin/python -m pytest tests/retrievers/test_filesystem.py -v`
Expected: 8 passed

- [ ] **Step 8: Commit**

```bash
git add code_reviewer/retrievers/filesystem.py tests/retrievers/test_filesystem.py
git commit -m "feat: add FilesystemRetriever for file:// URLs"
```

---

### Task 3: Wire `FilesystemRetriever` into routing, exports, and CLI help text

**Files:**
- Modify: `code_reviewer/agent.py:10-13` (imports), `code_reviewer/agent.py:22-29` (`route`)
- Modify: `code_reviewer/retrievers/__init__.py`
- Modify: `code_reviewer/cli.py:16`
- Test: `tests/test_agent.py`

- [ ] **Step 1: Write a failing routing test**

Add to `tests/test_agent.py`. First extend the import block at the top (after line 8):

```python
from code_reviewer.retrievers.filesystem import FilesystemRetriever
```

Then add this test next to the other `test_route_*` tests (after `test_route_sharepoint`, before `test_route_unknown_raises`):

```python
def test_route_filesystem():
    assert isinstance(route("file:///Users/anders/repo"), FilesystemRetriever)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_agent.py -v -k route_filesystem`
Expected: FAIL — `route()` raises `ValueError: Okänd URL-typ: file:///Users/anders/repo` instead of returning a `FilesystemRetriever`

- [ ] **Step 3: Add the import and routing branch in `agent.py`**

In `code_reviewer/agent.py`, change the import block (lines 10-13):

```python
from code_reviewer.retrievers.base import BaseRetriever, CodeFile
from code_reviewer.retrievers.gdrive import GoogleDriveRetriever
from code_reviewer.retrievers.github import GitHubRetriever
from code_reviewer.retrievers.onedrive import OneDriveRetriever
```

to:

```python
from code_reviewer.retrievers.base import BaseRetriever, CodeFile
from code_reviewer.retrievers.filesystem import FilesystemRetriever
from code_reviewer.retrievers.gdrive import GoogleDriveRetriever
from code_reviewer.retrievers.github import GitHubRetriever
from code_reviewer.retrievers.onedrive import OneDriveRetriever
```

Then update `route` (lines 22-29):

```python
def route(url: str) -> BaseRetriever:
    if "github.com" in url:
        return GitHubRetriever()
    if "drive.google.com" in url:
        return GoogleDriveRetriever()
    if "onedrive.live.com" in url or "sharepoint.com" in url:
        return OneDriveRetriever()
    raise ValueError(f"Okänd URL-typ: {url}")
```

to:

```python
def route(url: str) -> BaseRetriever:
    if "github.com" in url:
        return GitHubRetriever()
    if "drive.google.com" in url:
        return GoogleDriveRetriever()
    if "onedrive.live.com" in url or "sharepoint.com" in url:
        return OneDriveRetriever()
    if url.startswith("file://"):
        return FilesystemRetriever()
    raise ValueError(f"Okänd URL-typ: {url}")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_agent.py -v -k route_filesystem`
Expected: 1 passed

- [ ] **Step 5: Export `FilesystemRetriever` from the retrievers package**

Replace the contents of `code_reviewer/retrievers/__init__.py`:

```python
from .github import GitHubRetriever
from .gdrive import GoogleDriveRetriever
from .onedrive import OneDriveRetriever

__all__ = ["GitHubRetriever", "GoogleDriveRetriever", "OneDriveRetriever"]
```

with:

```python
from .github import GitHubRetriever
from .gdrive import GoogleDriveRetriever
from .onedrive import OneDriveRetriever
from .filesystem import FilesystemRetriever

__all__ = ["GitHubRetriever", "GoogleDriveRetriever", "OneDriveRetriever", "FilesystemRetriever"]
```

- [ ] **Step 6: Update the CLI help text for `--url`**

In `code_reviewer/cli.py`, change line 16:

```python
    parser.add_argument("--url", required=True, help="GitHub/Google Drive/OneDrive URL")
```

to:

```python
    parser.add_argument("--url", required=True, help="GitHub/Google Drive/OneDrive URL eller lokal sökväg (file:///abs/sökväg)")
```

- [ ] **Step 7: Run the full test suite to verify nothing is broken**

Run: `.venv/bin/python -m pytest -v`
Expected: all tests pass, including the new `test_route_filesystem`

- [ ] **Step 8: Commit**

```bash
git add code_reviewer/agent.py code_reviewer/retrievers/__init__.py code_reviewer/cli.py tests/test_agent.py
git commit -m "feat: route file:// URLs to FilesystemRetriever"
```

---

### Task 4: End-to-end manual verification

- [ ] **Step 1: Run a real review against a local directory**

Pick any small local TypeScript/C#/C++ project directory (or use this repo's own `code_reviewer/` — note it's Python, so the report will say `språk: "unknown"`; for a meaningful manual check, point at a TS/C#/C++ project if one is available locally). Run:

```bash
.venv/bin/code-reviewer --url file:///absolute/path/to/some/project --output /tmp/fs-review.json
```

Expected: command succeeds (assuming `ANTHROPIC_API_KEY` is set in `.env`), prints `Rapport sparad: /tmp/fs-review.json`, and the JSON contains a populated `språk` and review fields based on the local files.

- [ ] **Step 2: Verify error handling for a bad path**

```bash
.venv/bin/code-reviewer --url file:///no/such/directory
```

Expected: `Fel: Sökvägen finns inte eller är ingen katalog: /no/such/directory`, exit code 1 (caught by the existing `ValueError` handler in `cli.py:29-31`).

```bash
.venv/bin/code-reviewer --url file://relative/path
```

Expected: `Fel: file:// måste peka på en absolut sökväg, t.ex. file:///Users/.../repo: file://relative/path`, exit code 1.

---

## Self-review notes

- **Spec coverage:** URL format & routing → Task 3; `_parse_url` validation → Task 2; directory walking & filtering → Task 2; shared `should_include` refactor → Task 1; file read error handling → Task 2 (`test_fetch_skips_unreadable_files`); exports/CLI help → Task 3; tests → integrated into each task (TDD); manual end-to-end check → Task 4.
- **Type consistency:** `_parse_url` returns `Path` (used directly by `fetch` as `root`); `should_include(path: str, size: int) -> bool` signature matches between its definition (Task 1) and all call sites (Task 1's `github.py` update, Task 2's `filesystem.py`); `CodeFile(path, content, language)` matches `base.py`.
