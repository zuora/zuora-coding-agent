"""
Resolve the UAT workspace root (directory containing ``design/`` + ``execution/``).

Mixed repos default to ``<git-root>/uat/``. Dedicated test repos can use
``UAT_ROOT=.`` or ``root: .`` in ``.zuora-uat.yaml``.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

DEFAULT_UAT_DIR = "uat"
CONFIG_FILE = ".zuora-uat.yaml"
MARKER_FILE = ".zuora-uat-root"


def find_git_root(start: Path | None = None) -> Path:
    """Walk upward for a git repository root (or cwd)."""
    p = (start or Path.cwd()).resolve()
    for _ in range(40):
        if (p / ".git").exists():
            return p
        parent = p.parent
        if parent == p:
            break
        p = parent
    return (start or Path.cwd()).resolve()


def _has_standard_layout(root: Path) -> bool:
    return (root / "design").is_dir() and (root / "execution" / "tests").is_dir()


def _has_legacy_e2e_layout(root: Path) -> bool:
    return (root / "e2e" / "tests").is_dir()


def _has_any_uat_layout(root: Path) -> bool:
    return _has_standard_layout(root) or _has_legacy_e2e_layout(root)


def _resolve_relative_path(git_root: Path, relative: str) -> Path:
    rel = (relative or DEFAULT_UAT_DIR).strip()
    if rel in (".", ""):
        return git_root.resolve()
    path = Path(rel)
    if path.is_absolute():
        return path.resolve()
    return (git_root / rel).resolve()


def configured_uat_relative(git_root: Path) -> str | None:
    """Return configured UAT path relative to git root, or None if unset."""
    env = os.environ.get("UAT_ROOT", "").strip()
    if env:
        return env

    cfg_path = git_root / CONFIG_FILE
    if cfg_path.is_file():
        text = cfg_path.read_text(encoding="utf-8")
        if yaml is not None:
            data = yaml.safe_load(text) or {}
            if "root" in data and data["root"] is not None:
                return str(data["root"]).strip()
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                continue
            if stripped.startswith("root:"):
                return stripped.split(":", 1)[1].strip().strip("\"'")

    marker = git_root / MARKER_FILE
    if marker.is_file():
        return marker.read_text(encoding="utf-8").strip() or DEFAULT_UAT_DIR

    return None


def find_uat_root(git_root: Path | None = None, start: Path | None = None) -> Path:
    """Return the directory containing UAT ``design/`` + ``execution/`` (or legacy ``e2e/``)."""
    git = (git_root or find_git_root(start)).resolve()

    configured = configured_uat_relative(git)
    if configured is not None:
        return _resolve_relative_path(git, configured)

    uat_sub = (git / DEFAULT_UAT_DIR).resolve()
    if _has_any_uat_layout(uat_sub):
        return uat_sub
    if _has_any_uat_layout(git):
        return git
    return uat_sub


def default_scaffold_dir(git_root: Path | None = None) -> Path:
    """Target directory when scaffolding a new UAT workspace."""
    git = (git_root or find_git_root()).resolve()
    configured = configured_uat_relative(git)
    if configured is not None:
        return _resolve_relative_path(git, configured)
    return (git / DEFAULT_UAT_DIR).resolve()


def uat_relative_to_git(git_root: Path, uat_root: Path) -> str:
    """Express ``uat_root`` relative to ``git_root`` for display/config."""
    try:
        rel = uat_root.resolve().relative_to(git_root.resolve())
        return "." if rel.parts == () else rel.as_posix()
    except ValueError:
        return uat_root.as_posix()


def layout_info(git_root: Path | None = None, start: Path | None = None) -> dict:
    git = (git_root or find_git_root(start)).resolve()
    uat = find_uat_root(git)
    rel = configured_uat_relative(git)
    return {
        "git_root": str(git),
        "uat_root": str(uat),
        "uat_relative": uat_relative_to_git(git, uat),
        "configured_root": rel,
        "has_layout": _has_any_uat_layout(uat),
        "legacy_e2e": _has_legacy_e2e_layout(uat),
    }
