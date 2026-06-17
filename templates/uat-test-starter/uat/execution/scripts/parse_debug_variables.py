#!/usr/bin/env python3
"""Parse captured test variables from API debug logs for UI execution."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
_EXECUTION_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(_EXECUTION_DIR))
sys.path.insert(0, str(_EXECUTION_DIR / "tests"))

from tests.test_utils.uat_root import find_git_root, find_uat_root  # noqa: E402

_TR_KEY_RE = re.compile(r"^TR(\d+)$", re.I)
_RESPONSE_DATA_RE = re.compile(
    r"RESPONSE DATA:\s*\n(\{.*?\})\s*\n=+",
    re.DOTALL,
)
_DEBUG_VARIABLES_RE = re.compile(
    r"INFO:\s*DEBUG_VARIABLES:\s*(.+?)(?:\n|$)",
    re.MULTILINE,
)
_TEST_STATUS_RE = re.compile(r"^Status:\s*(PASSED|FAILED)\s*$", re.MULTILINE)


def _resolve_uat_root(args) -> Path:
    if getattr(args, "uat_root", None):
        return Path(args.uat_root).resolve()
    if getattr(args, "git_root", None):
        return find_uat_root(Path(args.git_root).resolve())
    return find_uat_root(find_git_root())


def normalize_tr_index(tr: str | int) -> str:
    text = str(tr).strip()
    if text.upper().startswith("TR"):
        return f"TR{int(text[2:])}"
    return f"TR{int(text)}"


def camel_to_snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def merge_response_variables(target: dict, payload: dict) -> None:
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, (dict, list)):
            continue
        target[camel_to_snake(key)] = value
        target[key] = value


def parse_debug_variables_line(line: str) -> dict[str, str]:
    variables: dict[str, str] = {}
    for token in line.strip().split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        variables[key.strip()] = value.strip()
    return variables


def parse_debug_log_text(text: str) -> dict:
    variables: dict = {}
    for match in _RESPONSE_DATA_RE.finditer(text):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            merge_response_variables(variables, payload)

    debug_line = _DEBUG_VARIABLES_RE.search(text)
    if debug_line:
        variables.update(parse_debug_variables_line(debug_line.group(1)))

    status_match = _TEST_STATUS_RE.search(text)
    api_test_passed = status_match.group(1) == "PASSED" if status_match else None
    return {
        "variables": variables,
        "api_test_passed": api_test_passed,
    }


def find_latest_debug_log(uat_root: Path, feature_id: str, tr_index: str) -> Path | None:
    tr_key = normalize_tr_index(tr_index)
    debug_dir = uat_root / "execution" / "debugging"
    if not debug_dir.is_dir():
        return None
    matches = sorted(
        debug_dir.glob(f"{feature_id}_{tr_key}_*.log"),
        key=lambda p: p.stat().st_mtime,
    )
    return matches[-1] if matches else None


def parse_debug_log_file(path: Path) -> dict:
    parsed = parse_debug_log_text(path.read_text(encoding="utf-8"))
    parsed["debug_log"] = str(path)
    return parsed


def cmd_parse(args):
    uat = _resolve_uat_root(args)
    tr_key = normalize_tr_index(args.tr)
    debug_log = find_latest_debug_log(uat, args.feature, tr_key)
    if debug_log is None:
        print(
            json.dumps(
                {
                    "feature": args.feature,
                    "tr": tr_key,
                    "debug_log": None,
                    "variables": {},
                    "api_test_passed": False,
                    "error": "debug_log_not_found",
                }
            )
        )
        sys.exit(1)

    result = parse_debug_log_file(debug_log)
    result["feature"] = args.feature
    result["tr"] = tr_key
    print(json.dumps(result))
    if result.get("api_test_passed") is False:
        sys.exit(2)


def main():
    parser = argparse.ArgumentParser(description="Parse variables from UAT API debug logs")
    parser.add_argument("--feature", required=True, help="Testmatrix feature id")
    parser.add_argument("--tr", required=True, help="TR number (1, TR1, etc.)")
    parser.add_argument("--git-root", help="Git project root (resolves UAT root)")
    parser.add_argument("--uat-root", help="UAT workspace root override")
    parser.set_defaults(func=cmd_parse)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
