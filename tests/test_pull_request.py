from __future__ import annotations

import subprocess
from pathlib import Path

from repocaster.config import Settings
from repocaster.pull_request import collect_pull_request_context, parse_pull_request_number


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def test_parse_pull_request_number_accepts_number_and_url():
    assert parse_pull_request_number("42") == 42
    assert parse_pull_request_number("https://github.com/time4116/repocaster/pull/42") == 42
    assert parse_pull_request_number("not a pull request") is None


def test_collect_pull_request_context_builds_synthetic_context_from_git_diff(tmp_path: Path):
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)],
        check=True,
        capture_output=True,
        text=True,
    )

    repo = tmp_path / "repo"
    subprocess.run(
        ["git", "clone", str(remote), str(repo)],
        check=True,
        capture_output=True,
        text=True,
    )
    _git(repo, "config", "user.name", "Tester")
    _git(repo, "config", "user.email", "tester@example.com")
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")
    _git(repo, "push", "origin", "HEAD:main")
    _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")

    _git(repo, "switch", "-c", "feature/pr-podcast")
    (repo / "README.md").write_text("# Demo\n\nPR focused podcast.\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "add podcast docs")
    _git(repo, "push", "origin", "HEAD:refs/pull/7/head")

    context_file = collect_pull_request_context(
        repo,
        "7",
        Settings(allowed_repos=("*",), allowed_users=("*",)),
    )

    assert context_file.path == "PULL_REQUEST.md"
    assert "Pull Request 7" in context_file.content
    assert "README.md" in context_file.content
    assert "PR focused podcast" in context_file.content
