import os

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
    os.symlink(tmp_path / "src" / "does-not-exist.ts", tmp_path / "src" / "broken_link.ts")  # dangling symlink — stat() raises FileNotFoundError
    r = FilesystemRetriever()

    files = r.fetch(f"file://{tmp_path}")

    paths = {f.path for f in files}
    assert "src/ok.ts" in paths
    assert "src/bad.ts" not in paths
    assert "src/broken_link.ts" not in paths


def test_fetch_respects_max_files(tmp_path):
    (tmp_path / "src").mkdir()
    for i in range(60):
        (tmp_path / "src" / f"file{i}.ts").write_text("const x = 1;")
    r = FilesystemRetriever()

    files = r.fetch(f"file://{tmp_path}")

    assert len(files) == 50
