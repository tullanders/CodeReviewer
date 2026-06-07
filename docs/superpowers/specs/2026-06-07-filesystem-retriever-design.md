# Filesystem-retriever — design

## Bakgrund

CodeReviewer har idag tre retrievers för att hämta källkod att granska: `GitHubRetriever`, `GoogleDriveRetriever` och `OneDriveRetriever`. Alla implementerar `BaseRetriever.fetch(url) -> list[CodeFile]` ([base.py:12-15](../../../code_reviewer/retrievers/base.py#L12-L15)) och routas via enkel strängmatchning i `agent.route()` ([agent.py:22-29](../../../code_reviewer/agent.py#L22-L29)).

Vi vill lägga till en fjärde retriever som läser kod direkt från det lokala filsystemet — t.ex. för att granska ett repo som redan finns klonat lokalt, utan att behöva pusha det någonstans.

## Mål

- En `FilesystemRetriever` som vandrar en lokal katalog och returnerar samma `CodeFile`-struktur som de övriga retrieverna.
- Routing som **inte krockar eller skuggar** de befintliga URL-mönstren (`github.com`, `drive.google.com`, `onedrive.live.com`/`sharepoint.com`).
- Konsekvent med befintliga mönster: samma filtreringsregler (`INCLUDE_EXTENSIONS`, `EXCLUDE_DIRS`, `MAX_FILE_SIZE_KB`, `MAX_FILES`), samma felhanteringsstil (`ValueError` med svenska meddelanden, fångas av befintlig CLI-hantering).

## Icke-mål

- Stöd för att peka på en enskild fil (endast kataloger, konsekvent med att övriga retrievers alltid hämtar ett helt träd).
- Stöd för relativa sökvägar, `~`-expansion eller annat än strikt `file:///abs/path`-syntax.
- Autentisering eller åtkomstkontroll (verktyget körs lokalt av den användare som redan har filsystemsåtkomst).

## URL-format & routing

Lokala kataloger anges med ett `file://`-prefix och en absolut sökväg, enligt RFC 8089-stil:

```
code-reviewer --url file:///Users/anders/projekt/mitt-repo
```

I `agent.route()` läggs en ny gren till:

```python
if url.startswith("file://"):
    return FilesystemRetriever()
```

`"file://"` kan aldrig matcha `"github.com"`, `"drive.google.com"` eller `"onedrive.live.com"`/`"sharepoint.com"` — grenens placering i `route()` spelar därför ingen roll för korrekthet, men läggs sist för att följa den visuella ordningen (github, gdrive, onedrive, filesystem).

CLI:ts hjälptext för `--url` ([cli.py:16](../../../code_reviewer/cli.py#L16)) uppdateras till att nämna `file://`-alternativet.

## Sökvägs-parsing

`_parse_url` strippar `"file://"`-prefixet och kräver:

1. Resten av strängen är en **absolut sökväg** (börjar med `/`). Annars: `ValueError` — "file:// måste peka på en absolut sökväg, t.ex. file:///Users/.../repo".
2. Sökvägen **existerar och är en katalog**. Annars: `ValueError` — "Sökvägen finns inte eller är ingen katalog: {path}".

Detta speglar `GitHubRetriever._parse_url` ([github.py:14-18](../../../code_reviewer/retrievers/github.py#L14-L18)) som också validerar och kastar `ValueError` vid ogiltig URL — vilket fångas av befintlig CLI-felhantering ([cli.py:29-31](../../../code_reviewer/cli.py#L29-L31)) utan ändringar där.

```python
def _parse_url(self, url: str) -> Path:
    raw = url.removeprefix("file://")
    path = Path(raw)
    if not path.is_absolute():
        raise ValueError(f"file:// måste peka på en absolut sökväg, t.ex. file:///Users/.../repo: {url}")
    if not path.is_dir():
        raise ValueError(f"Sökvägen finns inte eller är ingen katalog: {path}")
    return path
```

## Katalogvandring & filtrering

`fetch()` använder `os.walk(root, topdown=True)` och **beskär `EXCLUDE_DIRS` direkt i `dirnames`-listan** så att vandringen aldrig descenderar ner i t.ex. `node_modules`, `.git`, `dist` etc. Detta är avgörande lokalt — sådana mappar kan innehålla tiotusentals filer och skulle annars göra vandringen onödigt långsam.

För varje fil i en icke-exkluderad katalog:

1. Beräkna sökväg relativ till `root` via `Path(dirpath, name).relative_to(root)` — motsvarar `item["path"]` i GitHub-trädet och används för `CodeFile.path`, `detect_language()`, samt sortering/filtrering i `normalize()`.
2. Hämta filstorlek via `os.stat`.
3. Filtrera med en delad `should_include(path, size)` (se nästa avsnitt). Hoppa över filer som inte klarar filtret, utan att läsa deras innehåll.
4. Avbryt hela vandringen när `MAX_FILES` är nått.

## Delad filtreringslogik (refaktorering)

`GitHubRetriever._should_include(path, size)` ([github.py:20-26](../../../code_reviewer/retrievers/github.py#L20-L26)) filtrerar på `EXCLUDE_DIRS` + `INCLUDE_EXTENSIONS` + `MAX_FILE_SIZE_KB` — exakt den logik `FilesystemRetriever` också behöver, eftersom båda vandrar nästlade katalogträd (till skillnad från `gdrive.py`/`onedrive.py` som inte kontrollerar `EXCLUDE_DIRS`).

Som en liten, riktad förbättring flyttas denna logik till `normalizer.py` som en publik funktion `should_include(path: str, size: int) -> bool`, och både `GitHubRetriever` och `FilesystemRetriever` importerar och använder den. Beteendet ändras inte — bara var koden bor, vilket undviker en tredje kopia av samma sex rader.

```python
# normalizer.py
def should_include(path: str, size: int) -> bool:
    parts = Path(path).parts
    if any(part in EXCLUDE_DIRS for part in parts[:-1]):
        return False
    if Path(path).suffix not in INCLUDE_EXTENSIONS:
        return False
    return size <= MAX_FILE_SIZE_KB * 1024
```

`github.py` tar bort sin privata kopia och importerar `should_include` istället. Eftersom metoden då inte längre finns på `GitHubRetriever`, flyttas de befintliga testerna (`test_should_include_*` i [test_github.py:23-40](../../../tests/retrievers/test_github.py#L23-L40)) till `tests/test_normalizer.py` och anropar `should_include(...)` direkt som en fristående funktion, istället för `r._should_include(...)`.

## Läsning av filinnehåll & felhantering

Filer läses med `path.read_text(encoding="utf-8")`. Om läsningen misslyckas — `UnicodeDecodeError` (binärfil som råkar matcha en `INCLUDE_EXTENSION`), `OSError` (permission denied, trasig symlink, etc.) — **hoppas filen över tyst och vandringen fortsätter** med nästa fil:

```python
try:
    content = full_path.read_text(encoding="utf-8")
except (UnicodeDecodeError, OSError):
    continue
```

Detta håller granskningen robust mot enstaka konstiga filer i ett repo, utan att hela granskningen stoppas. Det skiljer sig medvetet från `_parse_url`, som *ska* stoppa granskningen direkt om hela sökvägen är ogiltig.

## Filstruktur & exporter

- Ny fil: `code_reviewer/retrievers/filesystem.py` med `FilesystemRetriever(BaseRetriever)`.
- `code_reviewer/retrievers/__init__.py`: lägg till import och `__all__`-post för `FilesystemRetriever`.
- `code_reviewer/agent.py`: importera `FilesystemRetriever`, lägg till routing-gren.
- `code_reviewer/cli.py`: uppdatera hjälptext för `--url`.
- `code_reviewer/normalizer.py`: lägg till publik `should_include(path, size)`.
- `code_reviewer/retrievers/github.py`: ta bort privat `_should_include`, importera och använd den delade funktionen.

## Tester

Ny `tests/retrievers/test_filesystem.py`, strukturerad som [test_github.py](../../../tests/retrievers/test_github.py) men med pytest:s `tmp_path`-fixture för att skapa riktiga kataloger/filer istället för att mocka HTTP (enklare och mer realistiskt för en lokal retriever):

- `_parse_url`: giltig absolut sökväg, relativ sökväg → fel, sökväg som inte finns → fel, sökväg som pekar på en fil (inte katalog) → fel.
- `fetch`: end-to-end mot en `tmp_path`-struktur med blandning av inkluderade/exkluderade filer (extension, storlek, exkluderade mappar som `node_modules`), verifierar `CodeFile.path` (relativ till root), `content`, `language`, samt att `MAX_FILES` respekteras.
- En binärfil eller fil med ogiltig encoding i strukturen → verifierar att den hoppas över tyst och övriga filer ändå returneras.

`should_include`-testerna ([test_github.py:23-40](../../../tests/retrievers/test_github.py#L23-L40)) flyttas till `tests/test_normalizer.py` som tester av den delade funktionen.

## Risker / avvägningar

- **Inga säkerhetsbarriärer**: `FilesystemRetriever` läser allt den har OS-behörighet till under den angivna katalogen. Detta är avsiktligt — verktyget körs lokalt av en betrodd användare med samma åtkomst, så ingen extra sandboxing läggs till (YAGNI).
- **`os.walk`-beskärning av `EXCLUDE_DIRS`** sker innan filtrering på extension/storlek görs, vilket är en medveten optimering: vi vill aldrig descendera in i t.ex. `node_modules` även om det skulle innehålla filer som matchar `INCLUDE_EXTENSIONS`.
