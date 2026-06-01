# Code Reviewer Agent — Design

**Datum:** 2026-05-31
**Status:** Godkänd

---

## Syfte

Ett CLI-verktyg som hämtar kandidaters kod från GitHub, Google Drive eller OneDrive och granskar den automatiskt via Claude API mot konfigurerbara kriterier. Resultatet är en strukturerad JSON-rapport som används som underlag inför live-intervju.

---

## Miljö & packaging

- **Pakethanterare:** `uv` + `pyproject.toml`
- **Installation:** `uv sync` (lokal) eller `uv tool install .` (global CLI)
- **Entry point:** `code-reviewer` → `code_reviewer.cli:main`
- **Konfiguration:** `.env`-fil via `python-dotenv`

```bash
# Installera globalt
uv tool install .

# Kör
code-reviewer --url "https://github.com/user/repo" --candidate abc123
```

---

## Arkitektur

```
code-reviewer/
  code_reviewer/
    retrievers/
      base.py          # abstrakt basklass (CodeFile, BaseRetriever)
      github.py        # GitHub REST API
      gdrive.py        # Google Drive API v3
      onedrive.py      # Microsoft Graph API
    agent.py           # router + orchestration
    normalizer.py      # filtrera, chunka, språkidentifiering
    prompts/
      review_ts.md     # prompt för TypeScript
      review_cs.md     # prompt för C#
      review_cpp.md    # prompt för C++
    cli.py             # entry point (main)
    config.py          # API-nycklar, inställningar
  output/              # JSON-rapporter per kandidat (gitignoreras)
  pyproject.toml
  .env.example
```

---

## Retrievers

### Basklass

```python
# code_reviewer/retrievers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class CodeFile:
    path: str
    content: str
    language: str

class BaseRetriever(ABC):
    @abstractmethod
    def fetch(self, url: str) -> list[CodeFile]:
        pass
```

### GitHub
- Publik repo: GitHub REST API utan auth
- Privat repo: Personal Access Token via `GITHUB_TOKEN`
- Hämtar filträd rekursivt: `GET /repos/{owner}/{repo}/git/trees/main?recursive=1`
- Hämtar filinnehåll: `GET /repos/{owner}/{repo}/contents/{path}`
- Filtrerar bort: `node_modules/`, `bin/`, `obj/`, `.git/`, byggfiler
- Gränser: max 200 filer, max 50 MB totalt

### Google Drive
- Autentisering: Service Account med JSON-nyckel (`GOOGLE_SERVICE_ACCOUNT_JSON`)
- Kandidaten delar mapp med "vem som har länken kan visa"
- Extraherar folder-ID från URL, listar filer rekursivt via Drive API v3

### OneDrive
- Autentisering: Microsoft Graph API med app-registrering (client credentials)
- Hämtar innehåll via `/shares/{encoded-url}/driveItem/children`
- Rekursiv traversering av undermappar

---

## Normalizer

```python
INCLUDE_EXTENSIONS = {'.ts', '.tsx', '.cs', '.cpp', '.h', '.hpp', '.py'}
EXCLUDE_DIRS = {'node_modules', 'bin', 'obj', '.git', 'dist', 'build', '__pycache__'}
MAX_FILE_SIZE_KB = 100
MAX_FILES = 50
```

- Filtrerar på extension och exkluderade mappar
- Hoppar över filer > `MAX_FILE_SIZE_KB`
- Chunkar stora filer vid behov
- Returnerar sorterad lista (tester sist)

---

## Router

```python
# code_reviewer/agent.py
def route(url: str) -> BaseRetriever:
    if 'github.com' in url:
        return GitHubRetriever()
    elif 'drive.google.com' in url:
        return GoogleDriveRetriever()
    elif 'onedrive.live.com' in url or 'sharepoint.com' in url:
        return OneDriveRetriever()
    else:
        raise ValueError(f'Okänd URL-typ: {url}')
```

---

## Prompt-hantering

- Promptfiler är externa `.md`-filer i `code_reviewer/prompts/`
- Väljs automatiskt baserat på majoritetsspråket (mest förekommande extension), eller anges explicit via `--prompt`
- Om inget klart majoritetsspråk finns och `--prompt` saknas: avbryt med felmeddelande
- Läses in vid körning — ingen omkompilering behövs vid promptändringar
- Innehåller: bedömningskriterier, poängskala 0–4, JSON output-format

### Poängskala
| Poäng | Innebär |
|-------|---------|
| 0 | Saknas helt / mycket bristfällig |
| 1 | Under förväntan |
| 2 | Godkänd |
| 3 | Bra |
| 4 | Exemplarisk |

### Bedömningsdimensioner
- **Korrekthet** — Löser koden problemet? Hanteras edge cases?
- **Läsbarhet** — Namngivning, struktur, kommentarer
- **Felhantering** — Exceptions, null-checks, robusthet
- **Testbarhet** — Finns tester? Är koden designad för testbarhet?
- **Idiomatik** — Används språket idiomatiskt?

---

## CLI

```bash
# Grundanvändning
code-reviewer --url "https://github.com/user/repo"

# Med explicit prompt
code-reviewer --url "https://drive.google.com/drive/folders/XYZ" --prompt code_reviewer/prompts/review_cs.md

# Med kandidat-ID och output-fil
code-reviewer \
  --url "https://github.com/user/repo" \
  --candidate "abc123" \
  --output output/abc123.json
```

---

## Miljövariabler

```env
ANTHROPIC_API_KEY=sk-...
GITHUB_TOKEN=ghp_...                    # valfri, för privata repos
GOOGLE_SERVICE_ACCOUNT_JSON=path/to.json
MS_TENANT_ID=...
MS_CLIENT_ID=...
MS_CLIENT_SECRET=...
```

---

## Output — JSON-rapport

```json
{
  "kandidat_id": "abc123",
  "url": "https://github.com/user/repo",
  "språk": "typescript",
  "tidsstämpel": "2026-05-31T10:00:00Z",
  "dimensioner": {
    "korrekthet":   { "poäng": 3, "motivering": "..." },
    "läsbarhet":    { "poäng": 4, "motivering": "..." },
    "felhantering": { "poäng": 2, "motivering": "..." },
    "testbarhet":   { "poäng": 3, "motivering": "..." },
    "idiomatik":    { "poäng": 3, "motivering": "..." }
  },
  "totalpoäng": 15,
  "styrkor": ["Ren arkitektur", "Konsekvent kodstil"],
  "svagheter": ["Saknar edge case-hantering för tom input"],
  "ai_indikationer": {
    "nivå": "låg",
    "flaggor": []
  },
  "frågor_till_live_session": [
    "Varför valde du den här datastrukturen på rad 78?",
    "Hur skulle du utöka lösningen för att hantera concurrent requests?"
  ]
}
```

---

## Beroenden

```toml
[project.dependencies]
anthropic = "*"
requests = "*"
google-api-python-client = "*"
google-auth = "*"
msal = "*"
python-dotenv = "*"
```

---

## Icke-funktionella krav

- Körning tar max 60 sekunder per kandidat
- Retrievers är isolerade — ny retriever kräver ingen ändring i övrig kod
- Promptfiler är den enda konfiguration som behöver ändras mellan rekryteringsomgångar
- Ingen kandidatkod lagras permanent — allt processas i minnet
- Loggar kandidat-ID och URL men inte kodinnehåll
