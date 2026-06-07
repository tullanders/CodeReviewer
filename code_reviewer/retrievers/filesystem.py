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
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]  # In-place mutation is what makes os.walk skip descending into excluded dirs
            for name in filenames:
                if len(files) >= MAX_FILES:
                    return files

                full_path = Path(dirpath) / name
                rel_path = full_path.relative_to(root).as_posix()

                try:
                    size = full_path.stat().st_size
                    if not should_include(rel_path, size):
                        continue
                    content = full_path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue  # Skip unreadable/binary/non-UTF-8/broken-symlink files — one bad file shouldn't abort the whole review

                files.append(
                    CodeFile(
                        path=rel_path,
                        content=content,
                        language=detect_language(rel_path),
                    )
                )
        return files
