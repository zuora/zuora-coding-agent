#!/usr/bin/env python3
"""Prepare hybrid TR context after API pytest for mandatory UI phase handoff."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
_EXECUTION_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(_EXECUTION_DIR))
sys.path.insert(0, str(_EXECUTION_DIR / "tests"))

from tests.test_utils.repo_paths import resolve_ui_steps_doc_path  # noqa: E402
from tests.test_utils.uat_root import find_git_root, find_uat_root  # noqa: E402

import parse_debug_variables as debug_parser  # noqa: E402


def _resolve_uat_root(args) -> Path:
    if getattr(args, "uat_root", None):
        return Path(args.uat_root).resolve()
    if getattr(args, "git_root", None):
        return find_uat_root(Path(args.git_root).resolve())
    return find_uat_root(find_git_root())


def _tenant_has_ui_auth(uat_root: Path, environment: str) -> bool:
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "tenant_resolve.py"),
        "--uat-root",
        str(uat_root),
        "--environment",
        environment,
    ]
    try:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except OSError:
        return False
    if proc.returncode != 0:
        return False
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return False
    return bool(payload.get("has_ui_auth"))


def prepare_hybrid_context(
    *,
    uat_root: Path,
    feature: str,
    tr: str | int,
    environment: str = "mcp",
) -> dict:
    tr_key = debug_parser.normalize_tr_index(tr)
    result: dict = {
        "feature": feature,
        "tr": tr_key,
        "hybrid": False,
        "ui_steps_path": None,
        "debug_log": None,
        "variables": {},
        "api_test_passed": False,
        "ui_auth_available": _tenant_has_ui_auth(uat_root, environment),
        "ui_phase_required": False,
        "execute_ui": False,
        "skip_reason": None,
    }

    try:
        ui_path = resolve_ui_steps_doc_path(feature, tr_key, uat_root)
    except (FileNotFoundError, ValueError):
        result["skip_reason"] = "no_ui_steps_doc"
        return result

    result["hybrid"] = True
    result["ui_phase_required"] = True
    result["ui_steps_path"] = str(ui_path)

    debug_log = debug_parser.find_latest_debug_log(uat_root, feature, tr_key)
    if debug_log is None:
        result["skip_reason"] = "debug_log_not_found"
        return result

    parsed = debug_parser.parse_debug_log_file(debug_log)
    result["debug_log"] = parsed["debug_log"]
    result["variables"] = parsed["variables"]
    result["api_test_passed"] = parsed.get("api_test_passed") is True

    if not result["api_test_passed"]:
        result["skip_reason"] = "api_test_not_passed"
        return result

    if not result["ui_auth_available"]:
        result["skip_reason"] = "no_ui_auth"
        return result

    result["execute_ui"] = True
    return result


def cmd_prepare(args):
    uat = _resolve_uat_root(args)
    result = prepare_hybrid_context(
        uat_root=uat,
        feature=args.feature,
        tr=args.tr,
        environment=args.environment,
    )
    print(json.dumps(result))
    if result["ui_phase_required"] and result["execute_ui"]:
        sys.exit(0)
    if result["ui_phase_required"] and not result["execute_ui"]:
        sys.exit(2)
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Prepare hybrid TR execution context")
    parser.add_argument("--feature", required=True)
    parser.add_argument("--tr", required=True)
    parser.add_argument("--environment", default="mcp")
    parser.add_argument("--git-root")
    parser.add_argument("--uat-root")
    parser.set_defaults(func=cmd_prepare)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
