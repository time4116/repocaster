from __future__ import annotations

import os
from dataclasses import dataclass


def _csv(name: str) -> list[str]:
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    allowed_repos: tuple[str, ...]
    allowed_users: tuple[str, ...]
    weekly_execution_limit: int = 2
    global_weekly_execution_limit: int = 5
    max_context_chars: int = 50_000
    max_files: int = 40
    max_file_chars: int = 8_000
    min_episode_minutes: int = 6
    max_episode_minutes: int = 8
    target_script_words: int = 1050
    min_script_words: int = 900
    max_script_words: int = 1400
    max_segments: int = 26
    s3_retention_days: int = 10
    presigned_url_ttl_seconds: int = 604_800
    bedrock_model_id: str = ""
    openai_tts_model: str = "tts-1-hd"
    openai_voice_a: str = "nova"
    openai_voice_b: str = "shimmer"
    output_bucket: str = ""

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            allowed_repos=tuple(_csv("ALLOWED_REPOS")),
            allowed_users=tuple(_csv("ALLOWED_USERS")),
            weekly_execution_limit=int(os.environ.get("WEEKLY_EXECUTION_LIMIT", "2")),
            global_weekly_execution_limit=int(os.environ.get("GLOBAL_WEEKLY_EXECUTION_LIMIT", "5")),
            max_context_chars=int(os.environ.get("MAX_CONTEXT_CHARS", "50000")),
            max_files=int(os.environ.get("MAX_FILES", "40")),
            max_file_chars=int(os.environ.get("MAX_FILE_CHARS", "8000")),
            min_episode_minutes=int(os.environ.get("MIN_EPISODE_MINUTES", "6")),
            max_episode_minutes=int(os.environ.get("MAX_EPISODE_MINUTES", "8")),
            target_script_words=int(os.environ.get("TARGET_SCRIPT_WORDS", "1050")),
            min_script_words=int(os.environ.get("MIN_SCRIPT_WORDS", "900")),
            max_script_words=int(os.environ.get("MAX_SCRIPT_WORDS", "1400")),
            max_segments=int(os.environ.get("MAX_SEGMENTS", "26")),
            s3_retention_days=int(os.environ.get("S3_RETENTION_DAYS", "10")),
            presigned_url_ttl_seconds=int(os.environ.get("S3_PRESIGNED_URL_TTL_SECONDS", "604800")),
            bedrock_model_id=os.environ.get("BEDROCK_MODEL_ID", ""),
            openai_tts_model=os.environ.get("OPENAI_TTS_MODEL", "tts-1-hd"),
            openai_voice_a=os.environ.get("OPENAI_TTS_VOICE_A", "nova"),
            openai_voice_b=os.environ.get("OPENAI_TTS_VOICE_B", "shimmer"),
            output_bucket=os.environ.get("OUTPUT_BUCKET", ""),
        )


def repo_allowed(full_name: str, settings: Settings) -> bool:
    if not settings.allowed_repos:
        return False
    if "*" in settings.allowed_repos:
        return True
    return full_name in settings.allowed_repos


def user_allowed(login: str, settings: Settings) -> bool:
    if not settings.allowed_users:
        return False
    if "*" in settings.allowed_users:
        return True
    return login in settings.allowed_users
