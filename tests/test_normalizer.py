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
    # .py is not a supported review language (no prompt file) so it maps to unknown
    assert detect_language("scripts/helper.py") == "unknown"

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
    assert result[1].path == "src/main.spec.ts"

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
