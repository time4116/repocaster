from __future__ import annotations

import shutil
import subprocess  # nosec B404
from pathlib import Path

from openai import OpenAI

from .config import Settings
from .script import PodcastScript, ScriptSegment


def _voice_for(segment: ScriptSegment, settings: Settings) -> str:
    return settings.openai_voice_a if segment.speaker == "HOST_A" else settings.openai_voice_b


def synthesize_segments_with_openai(
    script: PodcastScript,
    output_dir: Path,
    settings: Settings,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    client = OpenAI()
    segment_paths: list[Path] = []

    for index, segment in enumerate(script.segments, start=1):
        path = output_dir / f"segment-{index:03d}-{segment.speaker.lower()}.mp3"
        with client.audio.speech.with_streaming_response.create(
            model=settings.openai_tts_model,
            voice=_voice_for(segment, settings),
            input=segment.text,
            response_format="mp3",
        ) as response:
            response.stream_to_file(path)
        segment_paths.append(path)

    return segment_paths


def stitch_with_ffmpeg(segment_paths: list[Path], output_path: Path) -> None:
    if not segment_paths:
        raise ValueError("no audio segments to stitch")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    concat_file = output_path.parent / "segments.txt"
    concat_file.write_text(
        "\n".join(f"file '{path.resolve().as_posix()}'" for path in segment_paths) + "\n",
        encoding="utf-8",
    )
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for audio stitching")
    subprocess.run(  # nosec B603
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11",
            str(output_path),
        ],
        check=True,
    )
