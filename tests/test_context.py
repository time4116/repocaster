from pathlib import Path

from repocaster.config import Settings
from repocaster.context import build_context_pack


def test_focus_context_prioritizes_matching_files(tmp_path: Path):
    (tmp_path / "README.md").write_text("General repo docs", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "langchain_usage.py").write_text(
        "from langgraph.graph import StateGraph\n", encoding="utf-8"
    )
    (tmp_path / "src" / "other.py").write_text("print('hello')\n", encoding="utf-8")
    settings = Settings(allowed_repos=("*",), allowed_users=("*",), max_files=2)

    pack = build_context_pack(tmp_path, "focus", "LangGraph", settings)

    assert pack.files[0].path == "src/langchain_usage.py"
    assert pack.total_chars > 0


def test_context_ignores_secrets_and_media(tmp_path: Path):
    (tmp_path / ".env").write_text("OPENAI_API_KEY=secret", encoding="utf-8")
    (tmp_path / "podcast.mp3").write_bytes(b"fake")
    (tmp_path / "README.md").write_text("safe", encoding="utf-8")
    settings = Settings(allowed_repos=("*",), allowed_users=("*",))

    pack = build_context_pack(tmp_path, "architecture", None, settings)

    paths = {item.path for item in pack.files}
    assert "README.md" in paths
    assert ".env" not in paths
    assert "podcast.mp3" not in paths
