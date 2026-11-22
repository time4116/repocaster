from pathlib import Path

from repocaster.config import Settings
from repocaster.context import ContextFile, build_context_pack


def test_focus_context_prioritizes_matching_files(tmp_path: Path):
    (tmp_path / "README.md").write_text("General repo docs", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "langchain_usage.py").write_text(
        "from langgraph.graph import StateGraph\n", encoding="utf-8"
    )
    (tmp_path / "src" / "other.py").write_text("print('hello')\n", encoding="utf-8")
    settings = Settings(allowed_repos=("*",), allowed_users=("*",), max_files=2)

    pack = build_context_pack(tmp_path, "focus", "LangGraph", settings)

    assert pack.files[0].path == "src/langchain_usage.py"
    assert pack.total_chars > 0


def test_context_ignores_secrets_and_media(tmp_path: Path):
    (tmp_path / ".env").write_text("OPENAI_API_KEY=secret", encoding="utf-8")
    (tmp_path / "podcast.mp3").write_bytes(b"fake")
    (tmp_path / "README.md").write_text("safe", encoding="utf-8")
    settings = Settings(allowed_repos=("*",), allowed_users=("*",))

    pack = build_context_pack(tmp_path, "architecture", None, settings)

    paths = {item.path for item in pack.files}
    assert "README.md" in paths
    assert ".env" not in paths
    assert "podcast.mp3" not in paths


def test_context_excludes_credential_files_without_dropping_project_files(tmp_path: Path):
    excluded = (
        ".git-credentials",
        "nested/.git-credentials",
        ".config/gh/hosts.yml",
        "nested/.config/gh/hosts.yaml",
        ".config/gcloud/credentials.db",
        "nested/.config/gcloud/credentials.db",
        ".config/azure/accessTokens.json",
        "nested/.config/gh/hosts.yml",
        "infra/prod.tfplan",
        "infra/prod.tfplan.json",
        "infra/terraform.plan",
        "infra/terraform.tfplan",
        ".npmrc",
        ".pypirc",
        ".netrc",
        ".aws/credentials",
        ".aws/config",
        ".ssh/id_ed25519",
        ".config/gcloud/application_default_credentials.json",
        ".azure/accessTokens.json",
        ".kube/config",
        ".docker/config.json",
        "infra/terraform.tfstate",
        "infra/terraform.tfstate.backup",
        "infra/prod.tfvars",
        "infra/prod.tfvars.json",
        "certs/server.p12",
        "nested/.env.production",
        "nested/secrets.yml",
        "nested/credentials.json",
    )
    allowed = (
        "README.md",
        "package.json",
        "src/credentials.py",
        "infra/main.tf",
        "infra/variables.tf",
        "infra/plan.tf",
        "docs/terraform-plan.md",
        "infra/terraform.tfvars.example",
        ".env.example",
    )
    for name in (*excluded, *allowed):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture for {name}", encoding="utf-8")

    pack = build_context_pack(
        tmp_path,
        "architecture",
        "credentials",
        Settings(
            allowed_repos=("*",), allowed_users=("*",), max_files=100, max_context_chars=100_000
        ),
    )
    paths = {item.path for item in pack.files}
    assert paths.isdisjoint(excluded)
    assert paths.issuperset(allowed)
    assert all(f"fixture for {name}" not in pack.render() for name in excluded)


def test_context_applies_secret_exclusions_to_extra_files(tmp_path: Path):
    pack = build_context_pack(
        tmp_path,
        "focus",
        None,
        Settings(allowed_repos=("*",), allowed_users=("*",)),
        extra_files=(
            ContextFile(".aws/credentials", "SENTINEL_SECRET", 1_000),
            ContextFile("nested/.git-credentials", "SENTINEL_GIT_CREDENTIAL", 1_000),
            ContextFile("nested/.config/gh/hosts.yml", "SENTINEL_GH_CREDENTIAL", 1_000),
            ContextFile(
                "nested/.config/gcloud/credentials.db", "SENTINEL_GCLOUD_CREDENTIAL", 1_000
            ),
            ContextFile("infra/prod.tfplan", "SENTINEL_PLAN", 1_000),
            ContextFile("infra/terraform.plan", "SENTINEL_TERRAFORM_PLAN", 1_000),
            ContextFile("notes.md", "useful context", 900),
        ),
    )
    assert [item.path for item in pack.files] == ["notes.md"]
    assert "SENTINEL_SECRET" not in pack.render()


def test_context_ignores_symlinks_that_leave_repo(tmp_path: Path):
    outside = tmp_path.parent / "outside-secret.txt"
    outside.write_text("OPENAI_API_KEY=secret", encoding="utf-8")
    (tmp_path / "README.md").write_text("safe", encoding="utf-8")
    (tmp_path / "linked-secret.txt").symlink_to(outside)
    settings = Settings(allowed_repos=("*",), allowed_users=("*",))

    pack = build_context_pack(tmp_path, "architecture", None, settings)

    paths = {item.path for item in pack.files}
    rendered = pack.render()
    assert "README.md" in paths
    assert "linked-secret.txt" not in paths
    assert "OPENAI_API_KEY" not in rendered


def test_context_pack_prioritizes_pull_request_summary(tmp_path: Path):
    (tmp_path / "README.md").write_text("General repo docs", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "feature.py").write_text("print('hello')\n", encoding="utf-8")
    settings = Settings(allowed_repos=("*",), allowed_users=("*",), max_files=3)

    pack = build_context_pack(
        tmp_path,
        "focus",
        "review the pull request",
        settings,
        extra_files=(
            ContextFile(
                path="PULL_REQUEST.md",
                content="# Pull Request 42\n\nAdds the podcast feature.",
                score=1_000,
            ),
        ),
    )

    assert pack.files[0].path == "PULL_REQUEST.md"
    assert "Adds the podcast feature" in pack.render()
