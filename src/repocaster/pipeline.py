from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .audio import stitch_with_ffmpeg, synthesize_segments_with_openai
from .bedrock import generate_script_with_bedrock
from .config import Settings
from .context import ContextPack, build_context_pack
from .publish import publish_to_s3
from .script import PodcastScript, build_script_prompt


@dataclass(frozen=True)
class DryRunResult:
    context_pack: ContextPack
    prompt: str


@dataclass(frozen=True)
class PodcastResult:
    context_pack: ContextPack
    script: PodcastScript
    output_path: Path
    metadata_path: Path
    presigned_url: str | None = None


def generate_podcast_dry_run(
    repo_path: str,
    mode: str,
    focus: str | None,
    settings: Settings,
) -> DryRunResult:
    pack = build_context_pack(repo_path, mode, focus, settings)
    prompt = build_script_prompt(pack, settings)
    return DryRunResult(context_pack=pack, prompt=prompt)


def generate_podcast(
    repo_path: str,
    mode: str,
    focus: str | None,
    output_path: str,
    settings: Settings,
) -> PodcastResult:
    pack = build_context_pack(repo_path, mode, focus, settings)
    prompt = build_script_prompt(pack, settings)
    script = generate_script_with_bedrock(prompt, settings)
    output = Path(output_path)
    ensure_output_parent(str(output))
    segment_dir = output.parent / "segments"
    segment_paths = synthesize_segments_with_openai(script, segment_dir, settings)
    stitch_with_ffmpeg(segment_paths, output)
    metadata_path = output.with_suffix(".metadata.json")
    metadata = {
        "title": script.title,
        "mode": mode,
        "focus": focus,
        "target_duration_minutes": script.target_duration_minutes,
        "estimated_word_count": script.estimated_word_count,
        "segments": len(script.segments),
        "files": [item.path for item in pack.files],
        "total_context_chars": pack.total_chars,
        "output": str(output),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    presigned_url = publish_to_s3(output, metadata_path, settings)
    if presigned_url:
        metadata["presigned_url"] = presigned_url
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return PodcastResult(pack, script, output, metadata_path, presigned_url)


def ensure_output_parent(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
