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
