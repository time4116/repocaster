from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "create_actions_role.py"


def _load_create_actions_role():
    spec = importlib.util.spec_from_file_location("create_actions_role", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_bedrock_model_resource_scopes_foundation_model_id_to_region():
    module = _load_create_actions_role()
    assert (
        module.bedrock_model_resource("anthropic.claude-3-5-haiku-20241022-v1:0", "us-east-1")
        == "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-haiku-20241022-v1:0"
    )


def test_bedrock_model_resource_preserves_explicit_arn():
    module = _load_create_actions_role()
    arn = "arn:aws:bedrock:us-east-1::foundation-model/example-model"
    assert module.bedrock_model_resource(arn, "us-west-2") == arn


def test_bedrock_model_resource_rejects_non_bedrock_arn():
    module = _load_create_actions_role()
    with pytest.raises(ValueError, match="bedrock"):
        module.bedrock_model_resource("arn:aws:s3:::not-a-model", "us-east-1")


def test_create_actions_role_script_requires_bedrock_model_id():
    text = SCRIPT.read_text(encoding="utf-8")
    assert '"--bedrock-model-id"' in text
    assert "required=True" in text
    assert '"Resource": "*"' not in text
