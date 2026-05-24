from __future__ import annotations

import re

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


def script_word_count(script: PodcastScript) -> int:
    return sum(count_words(segment.text) for segment in script.segments)


def trim_script_to_word_limit(script: PodcastScript, max_words: int) -> PodcastScript:
    """Trim model output to the configured word ceiling as a last-resort guardrail.

    Bedrock can occasionally exceed explicit word-count instructions by a small amount.
    For owner-triggered MVP runs, returning a slightly trimmed episode is better than
    failing after the LLM call has already been paid for.
    """
    if script_word_count(script) <= max_words:
        return script

    remaining = max_words
    trimmed_segments: list[ScriptSegment] = []
    for segment in script.segments:
        words = [part for part in segment.text.split() if part.strip()]
        if not words:
            continue
        if remaining <= 0:
            break
        if len(words) <= remaining:
            trimmed_segments.append(segment)
            remaining -= len(words)
            continue
        trimmed_text = " ".join(words[:remaining]).rstrip(" ,;:")
        if not trimmed_text.endswith((".", "!", "?")):
            trimmed_text = f"{trimmed_text}."
        trimmed_segments.append(ScriptSegment(speaker=segment.speaker, text=trimmed_text))
        remaining = 0
        break

    return script.model_copy(
        update={
            "segments": trimmed_segments or script.segments[:1],
            "estimated_word_count": min(script.estimated_word_count, max_words),
        }
    )


def _looks_like_outro(segment: ScriptSegment) -> bool:
    text = segment.text.lower()
    outro_markers = (
        "to wrap up",
        "big takeaway",
        "thanks for listening",
        "in summary",
        "the takeaway",
        "so the takeaway",
        "final thought",
    )
    return any(marker in text for marker in outro_markers)


def trim_script_to_segment_limit(script: PodcastScript, max_segments: int) -> PodcastScript:
    """Trim model output to the configured segment ceiling as a last-resort guardrail.

    If the model included a recognizable closing segment, preserve it. A briefing that
    loses a middle detail is better than one that ends abruptly because the outro was
    sliced off.
    """
    if len(script.segments) <= max_segments:
        return script

    if max_segments <= 1:
        trimmed_segments = script.segments[:max_segments]
    elif _looks_like_outro(script.segments[-1]):
        trimmed_segments = [*script.segments[: max_segments - 1], script.segments[-1]]
    else:
        trimmed_segments = script.segments[:max_segments]

    return script.model_copy(
        update={
            "segments": trimmed_segments,
            "estimated_word_count": script_word_count(
                script.model_copy(update={"segments": trimmed_segments})
            ),
        }
    )


def normalize_spoken_terms(script: PodcastScript) -> PodcastScript:
    """Rewrite risky technical terms into forms that TTS reads more reliably."""
    replacements = (
        (re.compile(r"\bLangGraph\b"), "Lang Graph"),
        (re.compile(r"\bStateGraph\b"), "State Graph"),
        (re.compile(r"\bBedrock AgentCore\b"), "Bedrock Agent Core"),
        (re.compile(r"\bChatBedrockConverse\b"), "Chat Bedrock Converse"),
        (re.compile(r"\bSQS queue\b"), "S Q S queue"),
        (re.compile(r"\bSQS\b"), "S Q S"),
        (re.compile(r"\bidempotent comment design\b", re.IGNORECASE), "repeat-safe comment design"),
        (re.compile(r"\bidempotent comments\b", re.IGNORECASE), "repeat-safe comments"),
        (re.compile(r"\bidempotent\b", re.IGNORECASE), "repeat-safe"),
    )

    normalized_segments: list[ScriptSegment] = []
    changed = False
    for segment in script.segments:
        text = segment.text
        for pattern, replacement in replacements:
            text = pattern.sub(replacement, text)
        changed = changed or text != segment.text
        normalized_segments.append(segment.model_copy(update={"text": text}))

    if not changed:
        return script

    return script.model_copy(
        update={
            "segments": normalized_segments,
            "estimated_word_count": script_word_count(
                script.model_copy(update={"segments": normalized_segments})
            ),
        }
    )


def validate_script(script: PodcastScript, settings: Settings) -> None:
    words = script_word_count(script)
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
- Word count: strictly between {settings.min_script_words} and {settings.max_script_words} words
  total.
  Aim for {settings.target_script_words} words. Do not exceed {settings.max_script_words} words.
- Use exactly two speakers: HOST_A and HOST_B.
- Use at most {settings.max_segments} segments.
- Produce JSON only with fields: title, target_duration_minutes, estimated_word_count, segments.
- segments is an array of objects with speaker and text.
- Write for spoken audio, not an essay. Use short sentences and natural contractions.
- Avoid markdown, bullets, headings, and code syntax unless absolutely necessary.
- Natural handoffs between hosts should make the conversation feel like a polished
  technical podcast, not alternating summaries.
- Keep the middle section less implementation-heavy than raw code notes. Favor design
  decisions, tradeoffs, and why the pieces exist over exhaustive internals.
- Skip low-level parsing details unless they are central to the architecture or focus.
- Keep dense technical phrases readable aloud. Briefly explain repo-specific names
  before using them repeatedly.
- Pronunciation guidance: write terms in TTS-friendly spoken form, including Lang Graph,
  Claude, S Q S queue, Bedrock Agent Core, GitHub Actions, API Gateway, Lambda, and
  Terraform. Prefer "repeat-safe" over "idempotent" in spoken script text. Avoid
  phrasings that could be misread as "land graph," "cloud," "SQSQ," or "item potent."
- End with a short wrap-up that states the big takeaway and why the project is a strong
  architecture example. Do not end on a troubleshooting step or low-level detail.
- No markdown, no code blocks, no claims not supported by context.
- {focus_instruction}

Repository context:
{pack.render()}
""".strip()
