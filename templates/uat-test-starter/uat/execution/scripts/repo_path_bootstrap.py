"""Prepend ``execution/`` to ``sys.path`` so ``from tests.test_utils.repo_paths import …`` works in CLI scripts."""

from __future__ import annotations

import sys
from pathlib import Path


def ensure() -> None:
    execution_dir = Path(__file__).resolve().parent.parent
    s = str(execution_dir)
    if s not in sys.path:
        sys.path.insert(0, s)
