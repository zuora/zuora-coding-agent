#!/usr/bin/env python3
"""Discover feature groups for zuora-uat generate/run scope resolution.

Resolves UAT workspace under ``<git-root>/uat/`` by default (see ``uat_root.py``).

Usage:
    python discover_groups.py --git-root /path/to/project --features-input all
    python discover_groups.py --features-input "Feature_A[TR1-TR3],Feature_B"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent / "tests"))

from _feature_input_parser import (  # noqa: E402
    normalize_feature_stem,
    parse_feature_spec,
    split_features_bracket_aware,
)
from test_utils.uat_root import find_git_root, find_uat_root  # noqa: E402

try:
    import yaml
except ImportError:
    yaml = None


def _bootstrap_uat(uat_root: Path) -> None:
    execution_dir = uat_root / "execution"
    if execution_dir.is_dir():
        s = str(execution_dir)
        if s not in sys.path:
            sys.path.insert(0, s)
        return
    legacy = uat_root / "e2e"
    if legacy.is_dir():
        s = str(legacy)
        if s not in sys.path:
            sys.path.insert(0, s)


def design_paths(uat_root: Path) -> tuple[Path, Path]:
    if (uat_root / "design" / "testmatrix").is_dir() or (uat_root / "design").is_dir():
        return uat_root / "design" / "testmatrix", uat_root / "execution" / "tests" / "test_scenarios"
    return uat_root / "e2e" / "testmatrix", uat_root / "e2e" / "tests" / "test_scenarios"


def config_path(uat_root: Path) -> Path:
    for p in [
        uat_root / "execution" / "config" / "feature_groups.yaml",
        uat_root / "e2e" / "config" / "feature_groups.yaml",
    ]:
        if p.exists():
            return p
    return uat_root / "execution" / "config" / "feature_groups.yaml"


def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {"groups": []}
    text = config_path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text) or {"groups": []}
    return _parse_config_fallback(text)


def _parse_config_fallback(text: str) -> dict:
    groups = []
    current_group = None
    in_features = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            in_features = False if not stripped else in_features
            continue
        if stripped.startswith("- name:"):
            current_group = {"name": stripped.split(":", 1)[1].strip(), "display_name": "", "features": []}
            groups.append(current_group)
            in_features = False
        elif stripped.startswith("display_name:") and current_group is not None:
            current_group["display_name"] = stripped.split(":", 1)[1].strip().strip("\"'")
        elif stripped == "features:":
            in_features = True
        elif in_features and stripped.startswith("- ") and current_group is not None:
            current_group["features"].append(stripped[2:].strip())
        elif not stripped.startswith("-"):
            in_features = False
    return {"groups": groups}


def scan_testmatrix(testmatrix_dir: Path) -> list[str]:
    features: set[str] = set()
    if not testmatrix_dir.exists():
        return []
    for f in testmatrix_dir.iterdir():
        name = f.name
        if name.lower().endswith("_trs.md"):
            feat = name[: -len("_TRs.md")] if name.endswith("_TRs.md") else name[: -len("_trs.md")]
            features.add(feat)
    return sorted(features)


def find_test_folder(scenarios_dir: Path, feature_name: str) -> str | None:
    norm = feature_name.lower()
    exact = scenarios_dir / f"test_{norm}"
    if exact.is_dir():
        return exact.name
    for d in sorted(scenarios_dir.iterdir()):
        if d.is_dir() and d.name.startswith("test_"):
            folder_core = d.name[5:]
            if norm.startswith(folder_core) or folder_core.startswith(norm):
                return d.name
    for d in scenarios_dir.iterdir():
        if d.is_dir() and norm in d.name.lower():
            return d.name
    return None


def derive_prefix(feature_name: str) -> str:
    parts = feature_name.split("_")
    return parts[0] if len(parts) >= 2 else feature_name


def build_groups(config, all_features, scenarios_dir, features_filter=None, tr_filters=None):
    if tr_filters is None:
        tr_filters = {}
    if features_filter:
        filter_set = {normalize_feature_stem(f) for f in features_filter}
        all_features = [f for f in all_features if f in filter_set]

    feature_folders = {}
    for feat in all_features:
        folder = find_test_folder(scenarios_dir, feat)
        feature_folders[feat] = folder if folder else f"test_{feat.lower()}"

    assigned: set[str] = set()
    groups = []

    for grp in config.get("groups", []):
        group_features = []
        for feat in grp.get("features", []):
            if feat in feature_folders and feat in all_features:
                entry = {"feature": feat, "folder": feature_folders[feat]}
                if tr_filters.get(feat) is not None:
                    entry["tr_filter"] = tr_filters[feat]
                group_features.append(entry)
                assigned.add(feat)
        if group_features:
            groups.append({
                "name": grp["name"],
                "display_name": grp.get("display_name", grp["name"]),
                "features": group_features,
            })

    remaining = [f for f in all_features if f not in assigned and f in feature_folders]
    prefix_groups: dict[str, list] = {}
    for feat in remaining:
        prefix = derive_prefix(feat)
        entry = {"feature": feat, "folder": feature_folders[feat]}
        if tr_filters.get(feat) is not None:
            entry["tr_filter"] = tr_filters[feat]
        prefix_groups.setdefault(prefix, []).append(entry)

    for prefix in sorted(prefix_groups.keys()):
        groups.append({
            "name": prefix,
            "display_name": prefix,
            "features": prefix_groups[prefix][:],
        })

    return groups


def main():
    parser = argparse.ArgumentParser(description="Discover feature groups for UAT scope")
    parser.add_argument("--git-root", type=str, default=None, help="Git project root")
    parser.add_argument("--repo-root", type=str, default=None, help="Deprecated alias for --uat-root")
    parser.add_argument("--uat-root", type=str, default=None, help="UAT workspace root (overrides auto-detect)")
    parser.add_argument("--features-input", type=str, default="all")
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--testmatrix-dir", type=str, default=None)
    parser.add_argument("--scenarios-dir", type=str, default=None)
    args = parser.parse_args()

    git = Path(args.git_root).resolve() if args.git_root else find_git_root()
    if args.uat_root or args.repo_root:
        uat = Path(args.uat_root or args.repo_root).resolve()
    else:
        uat = find_uat_root(git)

    _bootstrap_uat(uat)
    tm_dir, scenarios_dir = design_paths(uat)
    if args.testmatrix_dir:
        tm_dir = Path(args.testmatrix_dir)
    if args.scenarios_dir:
        scenarios_dir = Path(args.scenarios_dir)

    cfg_path = Path(args.config) if args.config else config_path(uat)
    config = load_config(cfg_path)
    all_features = scan_testmatrix(tm_dir)

    if not all_features:
        print("[]")
        print(f"No features found in testmatrix under {tm_dir}", file=sys.stderr)
        sys.exit(0)

    features_filter = None
    tr_filters: dict = {}
    if args.features_input and args.features_input.strip().lower() != "all":
        raw_items = split_features_bracket_aware(args.features_input)
        features_filter = []
        for raw in raw_items:
            spec = parse_feature_spec(raw)
            features_filter.append(spec.stem)
            if spec.tr_filter is not None:
                tr_filters[spec.stem] = spec.tr_filter

    groups = build_groups(config, all_features, scenarios_dir, features_filter, tr_filters)
    print(json.dumps(groups, indent=None))

    total = sum(len(g["features"]) for g in groups)
    print(f"UAT root: {uat} (git: {git})", file=sys.stderr)
    print(f"Discovered {len(groups)} group(s) with {total} feature(s)", file=sys.stderr)


if __name__ == "__main__":
    main()
