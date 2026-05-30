from code_reviewer.retrievers.base import CodeFile


def test_codefile_fields():
    f = CodeFile(path="src/index.ts", content="const x = 1;", language="typescript")
    assert f.path == "src/index.ts"
    assert f.content == "const x = 1;"
    assert f.language == "typescript"
