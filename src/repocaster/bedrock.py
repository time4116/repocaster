from __future__ import annotations

import json

import boto3

from .config import Settings
from .script import PodcastScript, validate_script


def _extract_text(response: dict) -> str:
    parts = response.get("output", {}).get("message", {}).get("content", [])
    texts = [part.get("text", "") for part in parts if isinstance(part, dict) and part.get("text")]
    return "\n".join(texts).strip()


def generate_script_with_bedrock(prompt: str, settings: Settings) -> PodcastScript:
    if not settings.bedrock_model_id:
        raise ValueError("BEDROCK_MODEL_ID is required for non dry-run generation")

    client = boto3.client("bedrock-runtime")
    response = client.converse(
        modelId=settings.bedrock_model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 4096, "temperature": 0.2},
    )
    raw_text = _extract_text(response)
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        raw_text = raw_text.removeprefix("json").strip()
    script = PodcastScript.model_validate(json.loads(raw_text))
    validate_script(script, settings)
    return script
