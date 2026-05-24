from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
BINARY_SUFFIXES = {".pyc", ".mp3", ".wav", ".m4a", ".png", ".jpg", ".jpeg", ".gif", ".zip"}

HIGH_CONFIDENCE_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "github_classic_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "github_fine_grained_pat": re.compile(r"github_pat_[A-Za-z0-9_]{40,}"),
    "openai_legacy_key": re.compile(r"sk-[A-Za-z0-9]{20,}"),
    "openai_project_key": re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "jwt": re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}"),
    "slack_token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    "stripe_key": re.compile(r"(?:sk|rk)_live_[A-Za-z0-9]{20,}"),
    "npm_token": re.compile(r"npm_[A-Za-z0-9]{36}"),
}

SENSITIVE_METADATA_PATTERNS = {
    "aws_account_id": re.compile(r"(?<![0-9])[0-9]{12}(?![0-9])"),
    "aws_arn": re.compile(r"arn:aws[a-zA-Z-]*:[^:\s\"']*:[^:\s\"']*:\d{12}:[^\s\"']+"),
}

UNTRUSTED_SECRET_BEARING_TRIGGERS = {
    "pull_request",
    "pull_request_target",
    "workflow_run",
    "repository_dispatch",
    "issue_comment",
    "issues",
    "discussion",
    "discussion_comment",
    "schedule",
}

ALLOWED_REPOCASTER_SECRETS = {"AWS_ROLE_ARN", "BEDROCK_MODEL_ID", "OPENAI_API_KEY"}


def _tracked_files() -> list[Path]:
    output = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True)
    return [ROOT / line for line in output.splitlines() if line]


def _is_scannable(path: Path) -> bool:
    rel_parts = path.relative_to(ROOT).parts
    if any(part in EXCLUDED_PARTS for part in rel_parts):
        return False
    return path.suffix not in BINARY_SUFFIXES


def _workflow(path: str) -> dict[str, Any]:
    # BaseLoader avoids YAML 1.1 coercion of the key `on` into boolean True.
    return yaml.load((ROOT / path).read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def _trigger_names(workflow: dict[str, Any]) -> set[str]:
    on_value = workflow.get("on", {})
    if isinstance(on_value, str):
        return {on_value}
    if isinstance(on_value, list):
        return set(on_value)
    if isinstance(on_value, dict):
        return set(on_value)
    return set()


def _secret_refs(text: str) -> set[str]:
    refs = set(re.findall(r"secrets\.([A-Za-z_][A-Za-z0-9_]*)", text))
    refs.update(re.findall(r"secrets\[['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\]", text))
    dynamic_refs = re.findall(r"secrets\[([^'\"][^\]]*)\]", text)
    if dynamic_refs:
        refs.add("<dynamic-secret-reference>")
    return refs


def test_secret_reference_extractor_catches_dot_bracket_and_dynamic_forms():
    text = """
    env:
      A: ${{ secrets.OPENAI_API_KEY }}
      B: ${{ secrets['BEDROCK_MODEL_ID'] }}
      C: ${{ secrets[env.SECRET_NAME] }}
    """
    assert _secret_refs(text) == {
        "OPENAI_API_KEY",
        "BEDROCK_MODEL_ID",
        "<dynamic-secret-reference>",
    }


def test_tracked_files_do_not_contain_high_confidence_secrets_or_sensitive_metadata():
    findings: list[str] = []
    patterns = {**HIGH_CONFIDENCE_PATTERNS, **SENSITIVE_METADATA_PATTERNS}
    for path in _tracked_files():
        if not _is_scannable(path):
            continue
        text = path.read_text(errors="ignore")
        for name, pattern in patterns.items():
            if pattern.search(text):
                findings.append(f"{name}: {path.relative_to(ROOT)}")

    assert findings == []


def test_gitignore_semantically_blocks_local_secrets_and_generated_audio():
    should_be_ignored = [
        ".env",
        ".env.local",
        "private.pem",
        "github-app.key",
        "output/repocaster.mp3",
        "segments/segment-001.mp3",
        "cdk.out/template.json",
    ]
    result = subprocess.run(
        ["git", "check-ignore", *should_be_ignored],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    ignored = set(result.stdout.splitlines())
    assert set(should_be_ignored).issubset(ignored)


def test_action_and_workflow_pass_user_inputs_through_environment_variables():
    action_text = (ROOT / "action.yml").read_text(encoding="utf-8")
    workflow_text = (ROOT / ".github/workflows/repocaster.yml").read_text(encoding="utf-8")

    assert "REPOCASTER_FOCUS: ${{ inputs.focus }}" in action_text
    assert "REPOCASTER_FOCUS: ${{ inputs.focus }}" in workflow_text
    assert "REPOCASTER_MODE: ${{ inputs.mode }}" in workflow_text
    assert "REPOCASTER_REPOSITORY: ${{ inputs.repository }}" in action_text
    assert "repository: ${{ inputs.repository || github.repository }}" in workflow_text
    assert '--repo "$GITHUB_WORKSPACE/target-repo"' in workflow_text
    assert '--focus "${{ inputs.focus }}"' not in action_text
    assert '--focus "${{ inputs.focus }}"' not in workflow_text
    assert '--mode "${{ inputs.mode }}"' not in workflow_text


def test_action_can_checkout_and_analyze_a_different_repository():
    action = _workflow("action.yml")
    inputs = action.get("inputs", {})
    assert inputs.get("repository", {}).get("default") == ""
    assert inputs.get("ref", {}).get("default") == ""

    steps = action.get("runs", {}).get("steps", [])
    checkout_steps = [step for step in steps if step.get("uses") == "actions/checkout@v4"]
    assert checkout_steps
    assert checkout_steps[0].get("if") == "inputs.repository != ''"
    assert checkout_steps[0].get("with", {}).get("repository") == "${{ inputs.repository }}"
    assert checkout_steps[0].get("with", {}).get("path") == "repocaster-target"
    assert 'python -m pip install "$GITHUB_ACTION_PATH"' in (ROOT / "action.yml").read_text(
        encoding="utf-8"
    )


def test_owner_only_repocaster_workflow_has_only_manual_trigger_and_gated_jobs():
    workflow_path = ".github/workflows/repocaster.yml"
    workflow = _workflow(workflow_path)
    workflow_text = (ROOT / workflow_path).read_text(encoding="utf-8")

    assert _trigger_names(workflow) == {"workflow_dispatch"}
    assert _trigger_names(workflow).isdisjoint(UNTRUSTED_SECRET_BEARING_TRIGGERS)

    jobs = workflow.get("jobs", {})
    assert jobs
    for job_name, job in jobs.items():
        assert job.get("if") == "github.actor == 'time4116'", f"ungated job: {job_name}"

    assert _secret_refs(workflow_text) == ALLOWED_REPOCASTER_SECRETS


def test_ci_workflow_uses_read_only_permissions_and_no_secrets():
    workflow_path = ".github/workflows/test.yml"
    workflow = _workflow(workflow_path)
    workflow_text = (ROOT / workflow_path).read_text(encoding="utf-8")

    assert _trigger_names(workflow) == {"pull_request", "push"}
    assert _secret_refs(workflow_text) == set()

    permissions = workflow.get("permissions", {})
    assert permissions.get("contents") == "read"
    for scope, value in permissions.items():
        assert value != "write", f"unexpected write permission: {scope}"


def test_documented_storage_controls_are_present():
    docs = "\n".join(
        [
            (ROOT / "README.md").read_text(encoding="utf-8"),
            (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8"),
            (ROOT / "SECURITY.md").read_text(encoding="utf-8"),
        ]
    )
    assert "10 days" in docs
    assert "presigned URL" in docs or "presigned URLs" in docs
    assert "weekly quota" in docs or "weekly execution quotas" in docs
    assert "allowlist" in docs
