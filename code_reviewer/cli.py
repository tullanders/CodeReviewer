import argparse
import json
import os
import sys

from code_reviewer import agent


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="code-reviewer",
        description="Automatisk kodgranskning av rekryteringskandidater via Claude API",
    )
    parser.add_argument("--url", required=True, help="GitHub/Google Drive/OneDrive URL")
    parser.add_argument("--kandidat", default=None, metavar="ID", help="Kandidat-ID i output")
    parser.add_argument("--prompt", default=None, metavar="FIL", help="Sökväg till egen promptfil (.md)")
    parser.add_argument("--output", default=None, metavar="FIL", help="Sökväg till output JSON-fil (default: stdout)")

    args = parser.parse_args()

    try:
        result = agent.review(
            url=args.url,
            kandidat_id=args.kandidat,
            prompt_path=args.prompt,
        )
    except (ValueError, RuntimeError) as e:
        print(f"Fel: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print("Fel: Claude returnerade ogiltig JSON.", file=sys.stderr)
        sys.exit(1)

    output_json = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"Rapport sparad: {args.output}", file=sys.stderr)
    else:
        print(output_json)
