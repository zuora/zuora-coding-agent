#!/usr/bin/env python3
"""Print resolved git root and UAT workspace root as JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent / "tests"))

from test_utils.uat_root import layout_info  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Resolve UAT workspace root")
    parser.add_argument("--git-root", default=None, help="Git project root (default: auto-detect)")
    args = parser.parse_args()
    git = Path(args.git_root).resolve() if args.git_root else None
    print(json.dumps(layout_info(git), indent=2))


if __name__ == "__main__":
    main()
