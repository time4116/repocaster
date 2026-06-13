from __future__ import annotations

import fnmatch
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .config import Settings

IGNORE_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "output",
    "segments",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "cdk.out",
}
IGNORE_GLOBS = {
    "*.mp3",
    "*.wav",
    "*.m4a",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.zip",
    "*.pdf",
    "*.pem",
    "*.key",
    "*.egg-info/*",
    ".env",
    ".env.*",
}
PRIORITY_NAMES = {
    "README.md",
    "ARCHITECTURE.md",
    "ROADMAP.md",
    "SECURITY.md",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "Dockerfile",
    "docker-compose.yml",
}


@dataclass(frozen=True)
class ContextFile:
    path: str
    content: str
    score: int


@dataclass(frozen=True)
class ContextPack:
    repo_path: str
    mode: str
    focus: str | None
    files: tuple[ContextFile, ...]
    total_chars: int

    def render(self) -> str:
        parts = [f"Mode: {self.mode}", f"Focus: {self.focus or 'none'}", ""]
        for item in self.files:
            parts.append(f"--- FILE: {item.path} ---")
            parts.append(item.content)
        return "\n".join(parts)


def _ignored(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    if any(part in IGNORE_DIRS for part in rel.parts):
        return True
    rel_str = str(rel)
    return any(
        fnmatch.fnmatch(rel_str, pat) or fnmatch.fnmatch(path.name, pat) for pat in IGNORE_GLOBS
    )


def _safe_read(path: Path, max_chars: int) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\0" in raw[:2048]:
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return text[:max_chars]


def _tokens(text: str | None) -> set[str]:
    if not text:
        return set()
    return {tok.lower() for tok in re.findall(r"[A-Za-z0-9_+-]{3,}", text)}


def _score(path: Path, root: Path, content: str, focus: str | None) -> int:
    rel = str(path.relative_to(root))
    score = 0
    if path.name in PRIORITY_NAMES:
        score += 100
    if rel.startswith(".github/workflows/"):
        score += 80
    if "/src/" in f"/{rel}" or rel.startswith("src/"):
        score += 30
    if path.suffix in {".py", ".ts", ".tsx", ".js", ".mjs", ".yml", ".yaml", ".json", ".md"}:
        score += 20
    focus_tokens = _tokens(focus)
    if focus_tokens:
        haystack = f"{rel}\n{content[:4000]}".lower()
        score += 75 * sum(1 for tok in focus_tokens if tok in haystack)
    return score


def build_context_pack(
    repo_path: str | os.PathLike[str],
    mode: str,
    focus: str | None,
    settings: Settings,
    extra_files: tuple[ContextFile, ...] = (),
) -> ContextPack:
    root = Path(repo_path).resolve()
    candidates: list[ContextFile] = list(extra_files)
    for path in root.rglob("*"):
        if not path.is_file() or _ignored(path, root):
            continue
        content = _safe_read(path, settings.max_file_chars)
        if content is None:
            continue
        candidates.append(
            ContextFile(str(path.relative_to(root)), content, _score(path, root, content, focus))
        )

    chosen: list[ContextFile] = []
    total = 0
    for item in sorted(candidates, key=lambda f: (-f.score, f.path)):
        if len(chosen) >= settings.max_files:
            break
        if total + len(item.content) > settings.max_context_chars:
            remaining = settings.max_context_chars - total
            if remaining <= 0:
                break
            item = ContextFile(item.path, item.content[:remaining], item.score)
        chosen.append(item)
        total += len(item.content)

    return ContextPack(str(root), mode, focus, tuple(chosen), total)
