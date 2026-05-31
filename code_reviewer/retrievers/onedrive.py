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
