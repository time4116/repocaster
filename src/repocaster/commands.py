from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PodcastCommand:
    mode: str
    focus: str | None = None


def parse_podcast_command(body: str) -> PodcastCommand | None:
    stripped = body.strip()
    if not stripped.startswith("/podcast"):
        return None

    rest = stripped[len("/podcast") :].strip()
    if not rest:
        return PodcastCommand(mode="architecture")

    if rest.startswith("focus "):
        focus = rest[len("focus ") :].strip().strip('"').strip("'")
        if not focus:
            return None
        return PodcastCommand(mode="focus", focus=focus)

    if rest in {"architecture", "onboarding"}:
        return PodcastCommand(mode=rest)

    # Treat any free form suffix as a focus request; this keeps UX simple.
    return PodcastCommand(mode="focus", focus=rest.strip('"').strip("'"))
