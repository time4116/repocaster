from __future__ import annotations

import json
import re

import boto3

from .config import Settings
from .script import PodcastScript, trim_script_to_word_limit, validate_script


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
    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text.strip(), flags=re.IGNORECASE)
    raw_text = re.sub(r"\s*```$", "", raw_text)
    script = PodcastScript.model_validate(json.loads(raw_text))
    script = trim_script_to_word_limit(script, settings.max_script_words)
    validate_script(script, settings)
    return script
