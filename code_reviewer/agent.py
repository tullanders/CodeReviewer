import datetime
import json
import re
from importlib.resources import files as resource_files

import anthropic

from code_reviewer import config
from code_reviewer.normalizer import detect_majority_language, normalize
from code_reviewer.retrievers.base import BaseRetriever, CodeFile
from code_reviewer.retrievers.filesystem import FilesystemRetriever
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
    if url.startswith("file://"):
        return FilesystemRetriever()
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
        "tidsstämpel": datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z"),
        **result,
    }
