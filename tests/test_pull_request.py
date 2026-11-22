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
    (repo / "old.tfplan").write_text("SENTINEL_DELETED_PLAN", encoding="utf-8")
    (repo / "old.git-credentials").write_text("SENTINEL_RENAMED_CREDENTIAL", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "initial")
    _git(repo, "push", "origin", "HEAD:main")
    _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")

    _git(repo, "switch", "-c", "feature/pr-podcast")
    (repo / "README.md").write_text("# Demo\n\nPR focused podcast.\n", encoding="utf-8")
    (repo / ".npmrc").write_text("SENTINEL_NPM_CREDENTIAL", encoding="utf-8")
    (repo / ".git-credentials").write_text("SENTINEL_GIT_CREDENTIAL", encoding="utf-8")
    (repo / "old.tfplan").unlink()
    _git(repo, "mv", "old.git-credentials", ".git-credentials-renamed")
    (repo / ".git-credentials-renamed").write_text("SENTINEL_RENAMED_CREDENTIAL", encoding="utf-8")
    (repo / ".config" / "gh").mkdir(parents=True)
    (repo / ".config" / "gh" / "hosts.yml").write_text("SENTINEL_GH_CREDENTIAL", encoding="utf-8")
    (repo / "nested" / ".config" / "gh").mkdir(parents=True)
    (repo / "nested" / ".config" / "gh" / "hosts.yml").write_text(
        "SENTINEL_NESTED_GH", encoding="utf-8"
    )
    (repo / "nested" / ".git-credentials").write_text("SENTINEL_NESTED_GIT", encoding="utf-8")
    (repo / "nested" / ".config" / "gcloud").mkdir(parents=True)
    (repo / "nested" / ".config" / "gcloud" / "credentials.db").write_text(
        "SENTINEL_GCLOUD", encoding="utf-8"
    )
    (repo / "prod.tfplan").write_text("SENTINEL_PLAN", encoding="utf-8")
    (repo / "nested" / "terraform.plan").write_text("SENTINEL_TERRAFORM_PLAN", encoding="utf-8")
    (repo / "infra").mkdir()
    (repo / "infra" / "main.tf").write_text("# safe terraform source", encoding="utf-8")
    (repo / "infra" / "terraform.tfvars.example").write_text("# safe example", encoding="utf-8")
    (repo / ".aws").mkdir()
    (repo / ".aws" / "credentials").write_text("SENTINEL_AWS_CREDENTIAL", encoding="utf-8")
    (repo / ":(glob)*").write_text("safe unusual filename", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "add podcast docs")
    _git(repo, "push", "origin", "HEAD:refs/pull/7/head")

    context_file = collect_pull_request_context(
        repo,
        "7",
        Settings(allowed_repos=("*",), allowed_users=("*",), max_file_chars=100_000),
    )

    assert context_file.path == "PULL_REQUEST.md"
    assert "Pull Request 7" in context_file.content
    assert "README.md" in context_file.content
    assert "PR focused podcast" in context_file.content
    assert "safe unusual filename" in context_file.content
    assert "infra/main.tf" in context_file.content
    assert "infra/terraform.tfvars.example" in context_file.content
    for path in (
        "old.tfplan",
        "old.git-credentials",
        ".git-credentials-renamed",
        ".git-credentials",
        ".config/gh/hosts.yml",
        "nested/.config/gh/hosts.yml",
        "nested/.config/gcloud/credentials.db",
        "prod.tfplan",
        "nested/terraform.plan",
    ):
        assert path not in context_file.content
    for marker in (
        "SENTINEL_DELETED_PLAN",
        "SENTINEL_RENAMED_CREDENTIAL",
        "SENTINEL_GIT_CREDENTIAL",
        "SENTINEL_GH_CREDENTIAL",
        "SENTINEL_NESTED_GH",
        "SENTINEL_NESTED_GIT",
        "SENTINEL_GCLOUD",
        "SENTINEL_PLAN",
        "SENTINEL_TERRAFORM_PLAN",
    ):
        assert marker not in context_file.content
    assert ".npmrc" not in context_file.content
    assert ".aws/credentials" not in context_file.content
    assert "SENTINEL_NPM_CREDENTIAL" not in context_file.content
    assert "SENTINEL_AWS_CREDENTIAL" not in context_file.content
