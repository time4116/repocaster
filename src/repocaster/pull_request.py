from __future__ import annotations

import re
import shutil
# git is invoked with fixed argument vectors, never shell=True.
import subprocess  # nosec B404
from pathlib import Path

from .config import Settings
from .context import ContextFile

_PR_URL_RE = re.compile(r"github\.com/[^/]+/[^/]+/pull/(\d+)(?:\b|[/?#])")


def parse_pull_request_number(value: str | None) -> int | None:
    if not value:
        return None
    stripped = value.strip()
    if stripped.isdigit():
        number = int(stripped)
        return number if number > 0 else None
    match = _PR_URL_RE.search(stripped)
    if not match:
        return None
    return int(match.group(1))


def collect_pull_request_context(
    repo_path: str | Path,
    pull_request: str,
    settings: Settings,
) -> ContextFile:
    number = parse_pull_request_number(pull_request)
    if number is None:
        raise ValueError("pull_request must be a positive number or GitHub pull request URL")

    root = Path(repo_path).resolve()
    _git(root, "fetch", "--quiet", "origin", f"pull/{number}/head:refs/remotes/origin/pr-{number}")
    base_ref = _origin_head(root)
    head_ref = f"refs/remotes/origin/pr-{number}"
    merge_base = _git(root, "merge-base", base_ref, head_ref).strip()
    head_sha = _git(root, "rev-parse", "--short", head_ref).strip()
    stat = _git(root, "diff", "--stat", f"{merge_base}...{head_ref}").strip()
    files = _git(root, "diff", "--name-status", f"{merge_base}...{head_ref}").strip()
    diff = _git(
        root,
        "diff",
        "--find-renames",
        "--unified=80",
        f"{merge_base}...{head_ref}",
    )
    remaining = max(settings.max_file_chars - 600, 1_000)
    if len(diff) > remaining:
        diff = diff[:remaining] + "\n\n[diff truncated for podcast context]\n"

    content = "\n".join(
        [
            f"# Pull Request {number}",
            "",
            f"Head SHA: {head_sha}",
            f"Base ref: {base_ref}",
            "",
            "## Changed files",
            files or "No changed files detected.",
            "",
            "## Diff stat",
            stat or "No diff stat available.",
            "",
            "## Diff excerpt",
            diff.strip() or "No diff available.",
        ]
    )
    return ContextFile(
        path="PULL_REQUEST.md",
        content=content[: settings.max_file_chars],
        score=1_000,
    )


def _origin_head(repo: Path) -> str:
    try:
        return _git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").strip()
    except RuntimeError:
        return "origin/main"


def _git(repo: Path, *args: str) -> str:
    git = shutil.which("git") or "git"
    proc = subprocess.run(
        [git, *args],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )  # nosec B603
    if proc.returncode != 0:
        details = (proc.stderr or proc.stdout).strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {details}")
    return proc.stdout
