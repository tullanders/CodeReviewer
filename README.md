# code-reviewer

Automatically review candidate code from GitHub, Google Drive, or OneDrive using Claude AI. Produces a structured JSON report with scores, strengths, weaknesses, and suggested interview questions.

## What it does

Point `code-reviewer` at a candidate's repository or shared folder. It fetches the code, sends it to Claude with a language-specific review prompt, and returns a JSON report ready to use as interview prep.

```bash
code-reviewer --url "https://github.com/candidate/submission" --kandidat abc123
```

```json
{
  "kandidat_id": "abc123",
  "språk": "typescript",
  "tidsstämpel": "2026-05-31T10:00:00Z",
  "dimensioner": {
    "korrekthet":   { "poäng": 3, "motivering": "Löser huvudproblemet men saknar null-check på rad 42" },
    "läsbarhet":    { "poäng": 4, "motivering": "Konsekvent namngivning, välstrukturerat" },
    "felhantering": { "poäng": 2, "motivering": "Grundläggande try/catch men ingen loggning" },
    "testbarhet":   { "poäng": 3, "motivering": "Dependency injection används genomgående" },
    "idiomatik":    { "poäng": 3, "motivering": "Bra typdisciplin, undviker any" }
  },
  "totalpoäng": 15,
  "styrkor": ["Ren arkitektur", "Konsekvent kodstil"],
  "svagheter": ["Saknar edge case-hantering för tom input"],
  "ai_indikationer": { "nivå": "låg", "flaggor": [] },
  "frågor_till_live_session": [
    "Varför valde du den här datastrukturen på rad 78?",
    "Hur skulle du utöka lösningen för att hantera concurrent requests?"
  ]
}
```

## Supported languages

| Language   | Extensions            |
|------------|-----------------------|
| TypeScript | `.ts`, `.tsx`         |
| C#         | `.cs`                 |
| C++        | `.cpp`, `.h`, `.hpp`  |

## Supported sources

| Source       | Auth required                        |
|--------------|--------------------------------------|
| GitHub       | Optional (PAT for private repos)     |
| Google Drive | Service account JSON key             |
| OneDrive     | Azure app registration (client creds)|

## Installation

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/your-org/code-reviewer
cd code-reviewer
uv tool install .
```

Verify:

```bash
code-reviewer --help
```

## Configuration

Copy `.env.example` to `.env` and fill in the values you need:

```bash
cp .env.example .env
```

```env
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Optional — only needed for private GitHub repos
GITHUB_TOKEN=ghp_...

# Required for Google Drive sources
GOOGLE_SERVICE_ACCOUNT_JSON=/path/to/service-account.json

# Required for OneDrive/SharePoint sources
MS_TENANT_ID=...
MS_CLIENT_ID=...
MS_CLIENT_SECRET=...
```

## Usage

```bash
# GitHub (public repo)
code-reviewer --url "https://github.com/candidate/repo"

# GitHub (private repo, needs GITHUB_TOKEN)
code-reviewer --url "https://github.com/candidate/private-repo" --kandidat abc123

# Google Drive folder
code-reviewer --url "https://drive.google.com/drive/folders/FOLDER_ID"

# OneDrive shared folder
code-reviewer --url "https://onedrive.live.com/?id=..."

# Save report to file
code-reviewer --url "https://github.com/candidate/repo" \
  --kandidat abc123 \
  --output output/abc123.json

# Use a custom review prompt
code-reviewer --url "https://github.com/candidate/repo" \
  --prompt prompts/review_ts_senior.md
```

### Options

| Flag          | Description                                       |
|---------------|---------------------------------------------------|
| `--url`       | Repository or shared folder URL (required)        |
| `--kandidat`  | Candidate ID — included in the JSON report        |
| `--prompt`    | Path to a custom `.md` review prompt              |
| `--output`    | Write report to this file instead of stdout       |

## Scoring

Each dimension is scored 0–4:

| Score | Meaning              |
|-------|----------------------|
| 0     | Missing / very poor  |
| 1     | Below expectations   |
| 2     | Acceptable           |
| 3     | Good                 |
| 4     | Exemplary            |

Maximum total score is 20 (5 dimensions × 4).

## Custom prompts

Review prompts are plain Markdown files in `code_reviewer/prompts/`. Copy and modify one to create a custom review — no recompilation needed:

```bash
cp code_reviewer/prompts/review_ts.md prompts/review_ts_senior.md
# Edit scoring criteria, dimensions, etc.
code-reviewer --url "..." --prompt prompts/review_ts_senior.md
```

The prompt must instruct Claude to respond with valid JSON matching the output schema. See the existing prompts for reference.

## Development

```bash
# Install dev dependencies
uv sync --dev

# Run tests
uv run pytest

# Run the CLI without installing
uv run code-reviewer --help
```

## Limits

- Max 50 files per review
- Max 100 KB per file
- Max ~60 seconds per run

Files in `node_modules/`, `bin/`, `obj/`, `dist/`, `build/`, `.git/`, and `__pycache__/` are excluded automatically. Test files are included but sorted last.

## License

MIT
