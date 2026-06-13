from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import Settings
from .pipeline import generate_podcast, generate_podcast_dry_run
from .pull_request import parse_pull_request_number


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate an AI audio briefing from repository context."
    )
    parser.add_argument("--repo", required=True, help="Local repository path")
    parser.add_argument(
        "--mode",
        default="architecture",
        choices=["architecture", "focus", "onboarding"],
    )
    parser.add_argument("--focus", default="", help="Optional deep dive focus topic")
    parser.add_argument(
        "--pull-request",
        "--pr",
        default="",
        help="Optional pull request number or GitHub PR URL to ground the briefing in",
    )
    parser.add_argument("--output", default="output/repocaster.mp3")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build context/prompt only; no AI or TTS calls",
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    focus = args.focus.strip() or None
    pull_request = args.pull_request.strip() or None
    if pull_request and parse_pull_request_number(pull_request) is None:
        parser.error("--pull-request must be a positive number or GitHub pull request URL")

    if args.dry_run:
        result = generate_podcast_dry_run(args.repo, args.mode, focus, settings, pull_request)
        out_dir = Path(args.output).parent
        out_dir.mkdir(parents=True, exist_ok=True)
        metadata = {
            "mode": args.mode,
            "focus": focus,
            "pull_request": pull_request,
            "files": [item.path for item in result.context_pack.files],
            "total_chars": result.context_pack.total_chars,
            "prompt_chars": len(result.prompt),
        }
        Path(out_dir / "dry-run.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        print(json.dumps(metadata, indent=2))
        return

    result = generate_podcast(args.repo, args.mode, focus, args.output, settings, pull_request)
    print(
        json.dumps(
            {
                "title": result.script.title,
                "output": str(result.output_path),
                "metadata": str(result.metadata_path),
                "presigned_url": result.presigned_url,
                "segments": len(result.script.segments),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
