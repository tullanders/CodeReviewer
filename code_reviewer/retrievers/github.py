import re

import requests

from code_reviewer import config
from code_reviewer.normalizer import MAX_FILES, detect_language, should_include
from code_reviewer.retrievers.base import BaseRetriever, CodeFile

_URL_RE = re.compile(r"(?<![.\w])github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/|$)")


class GitHubRetriever(BaseRetriever):
    def _parse_url(self, url: str) -> tuple[str, str]:
        m = _URL_RE.search(url)
        if not m:
            raise ValueError(f"Kan inte parsa GitHub-URL: {url}")
        return m.group(1), m.group(2)

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
            if not should_include(item["path"], item.get("size", 0)):
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
