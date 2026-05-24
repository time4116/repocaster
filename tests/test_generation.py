from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

from repocaster.bedrock import generate_script_with_bedrock
from repocaster.config import Settings
from repocaster.script import PodcastScript, ScriptSegment


def _settings() -> Settings:
    return Settings(
        allowed_repos=("time4116/repocaster",),
        allowed_users=("time4116",),
        min_script_words=2,
        max_script_words=100,
        bedrock_model_id="test-model",
    )


def test_generate_script_with_bedrock_parses_and_validates_json():
    payload = {
        "title": "Repocaster",
        "target_duration_minutes": 6,
        "estimated_word_count": 4,
        "segments": [
            {"speaker": "HOST_A", "text": "hello repo"},
            {"speaker": "HOST_B", "text": "hello again"},
        ],
    }
    fake_client = Mock()
    fake_client.converse.return_value = {
        "output": {"message": {"content": [{"text": json.dumps(payload)}]}}
    }

    with patch("repocaster.bedrock.boto3.client", return_value=fake_client):
        script = generate_script_with_bedrock("prompt", _settings())

    assert script.title == "Repocaster"
    fake_client.converse.assert_called_once()


def test_stitch_with_ffmpeg_invokes_concat_command(tmp_path: Path):
    from repocaster.audio import stitch_with_ffmpeg

    seg1 = tmp_path / "one.mp3"
    seg2 = tmp_path / "two.mp3"
    seg1.write_bytes(b"one")
    seg2.write_bytes(b"two")
    output = tmp_path / "out.mp3"

    with (
        patch("repocaster.audio.shutil.which", return_value="/usr/bin/ffmpeg"),
        patch("repocaster.audio.subprocess.run") as run,
    ):
        stitch_with_ffmpeg([seg1, seg2], output)

    args = run.call_args.args[0]
    assert args[0] == "/usr/bin/ffmpeg"
    assert str(output) in args
    run.assert_called_once()


def test_publish_to_s3_skips_when_no_bucket(tmp_path: Path):
    from repocaster.publish import publish_to_s3

    settings = Settings(allowed_repos=(), allowed_users=())
    assert publish_to_s3(tmp_path / "a.mp3", tmp_path / "a.metadata.json", settings) is None


def test_pipeline_calls_bedrock_openai_ffmpeg_and_s3(tmp_path: Path):
    from repocaster.pipeline import generate_podcast

    script = PodcastScript(
        title="Repocaster",
        target_duration_minutes=6,
        estimated_word_count=4,
        segments=[ScriptSegment(speaker="HOST_A", text="hello repo")],
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Test repo", encoding="utf-8")

    with (
        patch("repocaster.pipeline.generate_script_with_bedrock", return_value=script),
        patch(
            "repocaster.pipeline.synthesize_segments_with_openai",
            return_value=[tmp_path / "seg.mp3"],
        ),
        patch("repocaster.pipeline.stitch_with_ffmpeg") as stitch,
        patch(
            "repocaster.pipeline.publish_to_s3", return_value="https://example.test/presigned"
        ) as publish,
    ):
        result = generate_podcast(
            str(repo),
            "architecture",
            None,
            str(tmp_path / "out" / "repocaster.mp3"),
            _settings(),
        )

    stitch.assert_called_once()
    publish.assert_called_once()
    assert result.presigned_url == "https://example.test/presigned"
    assert result.metadata_path.exists()
