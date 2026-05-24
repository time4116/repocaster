from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from .config import Settings
from .context import ContextPack


class ScriptSegment(BaseModel):
    speaker: str = Field(pattern=r"^HOST_[AB]$")
    text: str


class PodcastScript(BaseModel):
    title: str
    target_duration_minutes: int
    estimated_word_count: int
    segments: list[ScriptSegment]

    @field_validator("segments")
    @classmethod
    def require_segments(cls, value: list[ScriptSegment]) -> list[ScriptSegment]:
        if not value:
            raise ValueError("script must include at least one segment")
        return value


def count_words(text: str) -> int:
    return len([part for part in text.split() if part.strip()])


def validate_script(script: PodcastScript, settings: Settings) -> None:
    words = sum(count_words(segment.text) for segment in script.segments)
    if words < settings.min_script_words:
        raise ValueError(f"script too short: {words} words")
    if words > settings.max_script_words:
        raise ValueError(f"script too long: {words} words")
    if len(script.segments) > settings.max_segments:
        raise ValueError(f"too many segments: {len(script.segments)}")


def build_script_prompt(pack: ContextPack, settings: Settings) -> str:
    focus_instruction = (
        f"Focus the briefing on this topic: {pack.focus}. "
        "Do not summarize unrelated parts except when needed for context."
        if pack.mode == "focus" and pack.focus
        else "Create a broad architecture and onboarding briefing for the repository."
    )
    return f"""
You are Repocaster, an engineering briefing writer. Generate a two-host podcast script
grounded only in the repository context below.

Requirements:
- Target duration: {settings.min_episode_minutes} to {settings.max_episode_minutes} minutes.
- Word count: strictly between {settings.min_script_words} and {settings.max_script_words} words total.
  Aim for {settings.target_script_words} words. Do not exceed {settings.max_script_words} words.
- Use exactly two speakers: HOST_A and HOST_B.
- Produce JSON only with fields: title, target_duration_minutes, estimated_word_count, segments.
- segments is an array of objects with speaker and text.
- No markdown, no code blocks, no claims not supported by context.
- {focus_instruction}

Repository context:
{pack.render()}
""".strip()
