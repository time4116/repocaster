from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from repocaster.bedrock import generate_script_with_bedrock
from repocaster.config import Settings
from repocaster.script import (
    PodcastScript,
    ScriptSegment,
    build_script_prompt,
    normalize_spoken_terms,
)


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


def test_generate_script_with_bedrock_trims_overlong_model_output():
    payload = {
        "title": "Repocaster",
        "target_duration_minutes": 6,
        "estimated_word_count": 110,
        "segments": [
            {"speaker": "HOST_A", "text": " ".join(f"alpha{i}" for i in range(60))},
            {"speaker": "HOST_B", "text": " ".join(f"bravo{i}" for i in range(50))},
        ],
    }
    fake_client = Mock()
    fake_client.converse.return_value = {
        "output": {"message": {"content": [{"text": json.dumps(payload)}]}}
    }
    settings = _settings()

    with patch("repocaster.bedrock.boto3.client", return_value=fake_client):
        script = generate_script_with_bedrock("prompt", settings)

    total_words = sum(len(segment.text.split()) for segment in script.segments)
    assert total_words == settings.max_script_words
    assert script.estimated_word_count == settings.max_script_words


def test_generate_script_with_bedrock_trims_over_segmented_model_output():
    payload = {
        "title": "Repocaster",
        "target_duration_minutes": 6,
        "estimated_word_count": 6,
        "segments": [
            {"speaker": "HOST_A", "text": "one two"},
            {"speaker": "HOST_B", "text": "three four"},
            {"speaker": "HOST_A", "text": "five six"},
        ],
    }
    fake_client = Mock()
    fake_client.converse.return_value = {
        "output": {"message": {"content": [{"text": json.dumps(payload)}]}}
    }
    settings = Settings(
        allowed_repos=("time4116/repocaster",),
        allowed_users=("time4116",),
        min_script_words=2,
        max_script_words=100,
        max_segments=2,
        bedrock_model_id="test-model",
    )

    with patch("repocaster.bedrock.boto3.client", return_value=fake_client):
        script = generate_script_with_bedrock("prompt", settings)

    assert len(script.segments) == settings.max_segments
    assert script.estimated_word_count == 4
    assert [segment.text for segment in script.segments] == ["one two", "three four"]


def test_generate_script_with_bedrock_preserves_outro_when_trimming_segments():
    payload = {
        "title": "Repocaster",
        "target_duration_minutes": 6,
        "estimated_word_count": 10,
        "segments": [
            {"speaker": "HOST_A", "text": "opening context"},
            {"speaker": "HOST_B", "text": "middle detail"},
            {"speaker": "HOST_A", "text": "extra implementation"},
            {"speaker": "HOST_B", "text": "So to wrap up, this is the big takeaway."},
        ],
    }
    fake_client = Mock()
    fake_client.converse.return_value = {
        "output": {"message": {"content": [{"text": json.dumps(payload)}]}}
    }
    settings = Settings(
        allowed_repos=("time4116/repocaster",),
        allowed_users=("time4116",),
        min_script_words=2,
        max_script_words=100,
        max_segments=3,
        bedrock_model_id="test-model",
    )

    with patch("repocaster.bedrock.boto3.client", return_value=fake_client):
        script = generate_script_with_bedrock("prompt", settings)

    assert len(script.segments) == settings.max_segments
    assert [segment.text for segment in script.segments] == [
        "opening context",
        "middle detail",
        "So to wrap up, this is the big takeaway.",
    ]


def test_normalize_spoken_terms_rewrites_risky_tts_phrases():
    script = PodcastScript(
        title="LangGraph and StateGraph",
        target_duration_minutes=7,
        estimated_word_count=23,
        segments=[
            ScriptSegment(
                speaker="HOST_A",
                text="LangGraph sends work to an SQS queue before Bedrock AgentCore runs.",
            ),
            ScriptSegment(
                speaker="HOST_B",
                text=(
                    "The idempotent comment design reviews PRs with CI/CD context "
                    "through ChatBedrockConverse."
                ),
            ),
        ],
    )

    normalized = normalize_spoken_terms(script)
    joined = " ".join(segment.text for segment in normalized.segments)

    assert "Lang Graph" in joined
    assert "S Q S queue" in joined
    assert "Bedrock Agent Core" in joined
    assert "repeat-safe comment design" in joined
    assert "pull requests" in joined
    assert "C I C D" in joined
    assert "Chat Bedrock Converse" in joined
    assert "LangGraph" not in joined
    assert "SQS queue" not in joined
    assert "idempotent" not in joined.lower()


def test_generate_script_with_bedrock_normalizes_spoken_terms_before_tts():
    payload = {
        "title": "LangGraph",
        "target_duration_minutes": 6,
        "estimated_word_count": 12,
        "segments": [
            {
                "speaker": "HOST_A",
                "text": "LangGraph queues work in SQS and posts idempotent comments.",
            },
        ],
    }
    fake_client = Mock()
    fake_client.converse.return_value = {
        "output": {"message": {"content": [{"text": json.dumps(payload)}]}}
    }

    with patch("repocaster.bedrock.boto3.client", return_value=fake_client):
        script = generate_script_with_bedrock("prompt", _settings())

    assert script.segments[0].text == (
        "Lang Graph queues work in S Q S and posts repeat-safe comments."
    )


def test_generate_script_with_bedrock_strips_only_json_code_fence():
    payload = {
        "title": "Repocaster",
        "target_duration_minutes": 6,
        "estimated_word_count": 3,
        "segments": [{"speaker": "HOST_A", "text": "value keeps trailing ``` markers"}],
    }
    fake_client = Mock()
    fake_client.converse.return_value = {
        "output": {
            "message": {
                "content": [{"text": f"```json\n{json.dumps(payload)}\n```"}],
            }
        }
    }

    with patch("repocaster.bedrock.boto3.client", return_value=fake_client):
        script = generate_script_with_bedrock("prompt", _settings())

    assert script.segments[0].text.endswith("``` markers")


def test_settings_default_to_higher_quality_openai_tts_and_female_voices():
    settings = Settings(allowed_repos=(), allowed_users=())

    assert settings.openai_tts_model == "tts-1-hd"
    assert settings.openai_voice_a == "nova"
    assert settings.openai_voice_b == "shimmer"


def test_settings_from_env_default_to_higher_quality_openai_tts_and_female_voices(monkeypatch):
    monkeypatch.delenv("OPENAI_TTS_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_TTS_VOICE_A", raising=False)
    monkeypatch.delenv("OPENAI_TTS_VOICE_B", raising=False)

    settings = Settings.from_env()

    assert settings.openai_tts_model == "tts-1-hd"
    assert settings.openai_voice_a == "nova"
    assert settings.openai_voice_b == "shimmer"


def test_script_prompt_guides_bedrock_toward_spoken_audio_style(tmp_path: Path):
    from repocaster.context import ContextFile, ContextPack

    pack = ContextPack(
        repo_path=str(tmp_path),
        mode="architecture",
        focus=None,
        files=(ContextFile(path="README.md", content="# Repocaster", score=100),),
        total_chars=12,
    )

    prompt = build_script_prompt(pack, _settings())

    assert "Write for spoken audio, not an essay" in prompt
    assert "Use short sentences and natural contractions" in prompt
    assert "Avoid markdown, bullets, headings, and code syntax" in prompt
    assert "Natural handoffs between hosts" in prompt
    assert f"Use at most {_settings().max_segments} segments" in prompt


def test_script_prompt_requests_showcase_outro_and_less_dense_middle(tmp_path: Path):
    from repocaster.context import ContextFile, ContextPack

    pack = ContextPack(
        repo_path=str(tmp_path),
        mode="focus",
        focus="architecture and LangGraph",
        files=(ContextFile(path="README.md", content="# Bedrock PR Agent", score=100),),
        total_chars=18,
    )

    prompt = build_script_prompt(pack, _settings())

    assert "End with a short wrap-up" in prompt
    assert "big takeaway" in prompt
    assert "less implementation-heavy" in prompt
    assert "Skip low-level parsing details" in prompt


def test_script_prompt_includes_pronunciation_guidance_for_common_ai_terms(tmp_path: Path):
    from repocaster.context import ContextFile, ContextPack

    pack = ContextPack(
        repo_path=str(tmp_path),
        mode="architecture",
        focus=None,
        files=(ContextFile(path="README.md", content="# Bedrock PR Agent", score=100),),
        total_chars=18,
    )

    prompt = build_script_prompt(pack, _settings())

    assert "Pronunciation guidance" in prompt
    assert "Lang Graph" in prompt
    assert "Claude" in prompt
    assert "S Q S queue" in prompt
    assert "Bedrock Agent Core" in prompt
    assert "repeat-safe" in prompt


def test_openai_client_is_reused_for_all_segments(tmp_path: Path):
    from repocaster.audio import synthesize_segments_with_openai

    script = PodcastScript(
        title="Repocaster",
        target_duration_minutes=6,
        estimated_word_count=4,
        segments=[
            ScriptSegment(speaker="HOST_A", text="hello repo"),
            ScriptSegment(speaker="HOST_B", text="hello again"),
        ],
    )
    fake_client = Mock()
    fake_response = Mock()
    stream_context = MagicMock()
    stream_context.__enter__.return_value = fake_response
    fake_client.audio.speech.with_streaming_response.create.return_value = stream_context

    with patch("repocaster.audio.OpenAI", return_value=fake_client) as openai:
        paths = synthesize_segments_with_openai(script, tmp_path, _settings())

    openai.assert_called_once()
    assert len(paths) == 2
    assert fake_response.stream_to_file.call_count == 2


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
    assert "-af" in args
    assert "loudnorm=I=-16:TP=-1.5:LRA=11" in args
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
