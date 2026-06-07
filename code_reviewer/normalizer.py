from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from code_reviewer.retrievers.base import CodeFile

INCLUDE_EXTENSIONS = {".ts", ".tsx", ".cs", ".cpp", ".h", ".hpp"}
EXCLUDE_DIRS = {"node_modules", "bin", "obj", ".git", "dist", "build", "__pycache__"}
# MAX_FILE_SIZE_KB is exported for use by retrievers (GitHub, GDrive, OneDrive) to
# filter files before fetching content. CodeFile has no size field, so normalize()
# cannot apply this filter — it is enforced at fetch time by each retriever.
MAX_FILE_SIZE_KB = 100
MAX_FILES = 50

_EXT_TO_LANG: dict[str, str] = {
    ".ts": "typescript",
    ".tsx": "typescript",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
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


def should_include(path: str, size: int) -> bool:
    return _should_include(path) and size <= MAX_FILE_SIZE_KB * 1024


def normalize(files: list[CodeFile]) -> list[CodeFile]:
    included = [f for f in files if _should_include(f.path)]
    included.sort(key=lambda f: (1 if _is_test_file(f.path) else 0, f.path))
    return included[:MAX_FILES]


def detect_majority_language(files: list[CodeFile]) -> str:
    counts = Counter(f.language for f in files if f.language != "unknown")
    if not counts:
        return "unknown"
    return counts.most_common(1)[0][0]
