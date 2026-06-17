#!/usr/bin/env python3
"""Read/write per-feature .uat-verification.json manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
_EXECUTION_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(_EXECUTION_DIR))
sys.path.insert(0, str(_EXECUTION_DIR / "tests"))

from tests.test_utils.uat_root import find_git_root, find_uat_root  # noqa: E402

TR_ENTRY_KEY_RE = re.compile(r"^TR\d+$", re.I)
UI_STATUS_CHOICES = ("passed", "failed", "skipped")


def _resolve_uat_root(args) -> Path:
    if getattr(args, "uat_root", None):
        return Path(args.uat_root).resolve()
    if getattr(args, "git_root", None):
        return find_uat_root(Path(args.git_root).resolve())
    if getattr(args, "repo_root", None):
        return Path(args.repo_root).resolve()
    return find_uat_root(find_git_root())


def manifest_path(scenario_dir: Path) -> Path:
    return scenario_dir / ".uat-verification.json"


def artifact_paths(uat_root: Path, feature: str, tr_number: int) -> list[Path]:
    paths: list[Path] = []
    plan_dirs = list((uat_root / "design" / "testplan").glob(f"*{feature}*_Test_Plan"))
    if plan_dirs:
        plan_file = plan_dirs[0] / f"tr{tr_number}_test_design.md"
        if plan_file.is_file():
            paths.append(plan_file)
    scenario_dirs = list((uat_root / "execution" / "tests" / "test_scenarios").glob("test_*"))
    scenario = None
    norm = feature.lower()
    for d in scenario_dirs:
        core = d.name[5:]
        if norm == core or norm.startswith(core) or core.startswith(norm):
            scenario = d
            break
    if scenario:
        for pattern in (f"*_tr{tr_number}_api.py", f"ui_steps_tr{tr_number}.md"):
            for p in scenario.glob(pattern):
                paths.append(p)
    return paths


def compute_artifact_revision(uat_root: Path, feature: str, tr_number: int) -> str:
    paths = artifact_paths(uat_root, feature, tr_number)
    h = hashlib.sha256()
    for p in sorted(paths, key=lambda x: str(x)):
        h.update(str(p).encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:12] if paths else ""


def load_manifest(scenario_dir: Path) -> dict:
    path = manifest_path(scenario_dir)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(scenario_dir: Path, data: dict) -> None:
    scenario_dir.mkdir(parents=True, exist_ok=True)
    manifest_path(scenario_dir).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def tr_key(tr_number: int) -> str:
    return f"TR{tr_number}"


def find_scenario_dir(uat_root: Path, feature: str) -> Path | None:
    scenarios_root = uat_root / "execution" / "tests" / "test_scenarios"
    norm = feature.lower()
    for d in sorted(scenarios_root.glob("test_*")):
        if not d.is_dir():
            continue
        core = d.name[5:]
        if norm == core or norm.startswith(core) or core.startswith(norm):
            return d
    return None


def list_tr_numbers(uat_root: Path, feature: str, tr_filter: list[int] | None = None) -> list[int]:
    trs: set[int] = set()
    plan_dirs = list((uat_root / "design" / "testplan").glob(f"*{feature}*_Test_Plan"))
    if plan_dirs:
        for plan_file in plan_dirs[0].glob("tr*_test_design.md"):
            match = re.search(r"tr(\d+)_test_design\.md$", plan_file.name, re.I)
            if match:
                trs.add(int(match.group(1)))
    if not trs:
        scenario = find_scenario_dir(uat_root, feature)
        if scenario:
            for api_file in scenario.glob("*_tr*_api.py"):
                match = re.search(r"_tr(\d+)_api\.py$", api_file.name, re.I)
                if match:
                    trs.add(int(match.group(1)))
    result = sorted(trs)
    if tr_filter is not None:
        allowed = set(tr_filter)
        result = [tr for tr in result if tr in allowed]
    return result


def validate_manifest(data: dict) -> list[str]:
    errors: list[str] = []
    if not data:
        errors.append("manifest is empty")
        return errors

    for key, entry in data.items():
        if not TR_ENTRY_KEY_RE.match(str(key)):
            errors.append(f"non-canonical top-level key: {key!r}")
            continue
        if not isinstance(entry, dict):
            errors.append(f"{key} entry must be an object")
            continue
        if "verified" not in entry or not isinstance(entry["verified"], bool):
            errors.append(f"{key} missing boolean verified field")
        ui = entry.get("ui")
        if ui is not None:
            if not isinstance(ui, dict):
                errors.append(f"{key}.ui must be an object")
            elif ui.get("status") not in UI_STATUS_CHOICES:
                errors.append(f"{key}.ui.status must be one of {UI_STATUS_CHOICES}")
    return errors


def is_legacy_manifest(data: dict) -> bool:
    if not data:
        return False
    return any(not TR_ENTRY_KEY_RE.match(str(key)) for key in data)


def _clear_tr(scenario_dir: Path, tr_number: int) -> dict:
    data = load_manifest(scenario_dir)
    key = tr_key(tr_number)
    previous = data.get(key, {})
    entry = {"verified": False}
    if isinstance(previous, dict) and previous.get("ui"):
        entry["ui"] = previous["ui"]
    data[key] = entry
    save_manifest(scenario_dir, data)
    return data[key]


def _add_root_args(p):
    p.add_argument("--git-root", help="Git project root (resolves UAT root)")
    p.add_argument("--uat-root", help="UAT workspace root override")
    p.add_argument("--repo-root", help="Deprecated: UAT workspace root")


def cmd_revision(args):
    uat = _resolve_uat_root(args)
    print(compute_artifact_revision(uat, args.feature, int(args.tr)))


def cmd_get(args):
    data = load_manifest(Path(args.scenario_dir))
    print(json.dumps(data.get(tr_key(int(args.tr)), {})))


def cmd_set(args):
    scenario = Path(args.scenario_dir)
    data = load_manifest(scenario)
    key = tr_key(int(args.tr))
    entry: dict = {"verified": args.verified.lower() == "true"}
    if entry["verified"] and args.feature:
        uat = _resolve_uat_root(args)
        entry["verified_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        entry["artifact_revision"] = compute_artifact_revision(uat, args.feature, int(args.tr))
    elif not entry["verified"] and args.reason:
        entry["reason"] = args.reason
    previous = data.get(key, {})
    if isinstance(previous, dict) and previous.get("ui"):
        entry["ui"] = previous["ui"]
    data[key] = entry
    save_manifest(scenario, data)
    print(json.dumps(entry))


def cmd_clear(args):
    scenario = Path(args.scenario_dir)
    entry = _clear_tr(scenario, int(args.tr))
    print(json.dumps(entry))


def cmd_finalize_generate(args):
    uat = _resolve_uat_root(args)
    scenario = find_scenario_dir(uat, args.feature)
    if scenario is None:
        print(json.dumps({"feature": args.feature, "verification": {}, "error": "scenario_dir_not_found"}))
        sys.exit(1)

    tr_filter = [int(tr) for tr in args.tr] if args.tr else None
    tr_numbers = list_tr_numbers(uat, args.feature, tr_filter)
    verification: dict[str, dict] = {}

    if args.verify.lower() == "false":
        for tr_number in tr_numbers:
            verification[tr_key(tr_number)] = _clear_tr(scenario, tr_number)

    manifest = load_manifest(scenario)
    validation_errors = validate_manifest(manifest)
    print(
        json.dumps(
            {
                "feature": args.feature,
                "verification": verification,
                "manifest_path": str(manifest_path(scenario)),
                "validation_errors": validation_errors,
            }
        )
    )


def cmd_should_verify(args):
    data = load_manifest(Path(args.scenario_dir))
    entry = data.get(tr_key(int(args.tr)), {})
    if not entry.get("verified"):
        sys.exit(0)
    if not args.feature:
        sys.exit(1)
    uat = _resolve_uat_root(args)
    current = compute_artifact_revision(uat, args.feature, int(args.tr))
    stored = entry.get("artifact_revision", "")
    sys.exit(0 if current != stored else 1)


def cmd_validate(args):
    scenario = Path(args.scenario_dir)
    if not manifest_path(scenario).is_file():
        print(json.dumps({"valid": False, "errors": ["manifest_missing"], "legacy": False}))
        sys.exit(1)
    data = load_manifest(scenario)
    errors = validate_manifest(data)
    payload = {
        "valid": not errors,
        "errors": errors,
        "legacy": is_legacy_manifest(data),
        "manifest_path": str(manifest_path(scenario)),
    }
    print(json.dumps(payload))
    sys.exit(0 if payload["valid"] else 1)


def cmd_ensure_manifest(args):
    uat = _resolve_uat_root(args)
    scenario = find_scenario_dir(uat, args.feature)
    if scenario is None:
        print(json.dumps({"feature": args.feature, "error": "scenario_dir_not_found"}))
        sys.exit(1)

    tr_filter = [int(tr) for tr in args.tr] if args.tr else None
    tr_numbers = list_tr_numbers(uat, args.feature, tr_filter)
    path = manifest_path(scenario)
    recreated = False
    backup_path = None
    added: dict[str, dict] = {}

    if path.is_file():
        data = load_manifest(scenario)
        errors = validate_manifest(data)
        if errors or is_legacy_manifest(data):
            backup_path = path.with_suffix(".json.bak")
            backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            save_manifest(scenario, {})
            recreated = True
            data = {}
        for tr_number in tr_numbers:
            key = tr_key(tr_number)
            if key not in data:
                added[key] = _clear_tr(scenario, tr_number)
    else:
        recreated = True
        for tr_number in tr_numbers:
            key = tr_key(tr_number)
            added[key] = _clear_tr(scenario, tr_number)

    validation_errors = validate_manifest(load_manifest(scenario))
    print(
        json.dumps(
            {
                "feature": args.feature,
                "manifest_path": str(path),
                "recreated": recreated,
                "backup_path": str(backup_path) if backup_path else None,
                "added": added,
                "validation_errors": validation_errors,
            }
        )
    )
    if validation_errors:
        sys.exit(1)


def cmd_record_ui_result(args):
    scenario = Path(args.scenario_dir)
    data = load_manifest(scenario)
    key = tr_key(int(args.tr))
    entry = data.get(key, {"verified": False})
    if not isinstance(entry, dict):
        entry = {"verified": False}

    ui_entry: dict = {
        "status": args.status,
        "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if args.evidence:
        ui_entry["evidence"] = args.evidence
    if args.summary:
        ui_entry["summary"] = args.summary
    if args.reason:
        ui_entry["reason"] = args.reason

    entry["ui"] = ui_entry
    data[key] = entry
    save_manifest(scenario, data)
    print(json.dumps({"tr": key, "ui": ui_entry}))


def main():
    parser = argparse.ArgumentParser(description="UAT verification manifest helpers")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("revision")
    _add_root_args(p)
    p.add_argument("--feature", required=True)
    p.add_argument("--tr", required=True)
    p.set_defaults(func=cmd_revision)

    p = sub.add_parser("get")
    p.add_argument("--scenario-dir", required=True)
    p.add_argument("--tr", required=True)
    p.set_defaults(func=cmd_get)

    p = sub.add_parser("set")
    _add_root_args(p)
    p.add_argument("--scenario-dir", required=True)
    p.add_argument("--tr", required=True)
    p.add_argument("--verified", required=True, choices=["true", "false"])
    p.add_argument("--feature")
    p.add_argument("--reason")
    p.set_defaults(func=cmd_set)

    p = sub.add_parser("clear")
    p.add_argument("--scenario-dir", required=True)
    p.add_argument("--tr", required=True)
    p.set_defaults(func=cmd_clear)

    p = sub.add_parser("should-verify")
    _add_root_args(p)
    p.add_argument("--scenario-dir", required=True)
    p.add_argument("--tr", required=True)
    p.add_argument("--feature")
    p.set_defaults(func=cmd_should_verify)

    p = sub.add_parser("finalize-generate")
    _add_root_args(p)
    p.add_argument("--feature", required=True)
    p.add_argument("--verify", required=True, choices=["true", "false"])
    p.add_argument("--tr", action="append")
    p.set_defaults(func=cmd_finalize_generate)

    p = sub.add_parser("validate")
    p.add_argument("--scenario-dir", required=True)
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("ensure-manifest")
    _add_root_args(p)
    p.add_argument("--feature", required=True)
    p.add_argument("--tr", action="append")
    p.set_defaults(func=cmd_ensure_manifest)

    p = sub.add_parser("record-ui-result")
    p.add_argument("--scenario-dir", required=True)
    p.add_argument("--tr", required=True)
    p.add_argument("--status", required=True, choices=list(UI_STATUS_CHOICES))
    p.add_argument("--evidence")
    p.add_argument("--summary")
    p.add_argument("--reason")
    p.set_defaults(func=cmd_record_ui_result)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
