#!/usr/bin/env python3
"""Zuora workflow engine CLI — lookup, validate-plan, build."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from workflow_engine.build_workflow import build_workflow_definition
from workflow_engine.validate_tool import validate_workflow_plan
from workflow_engine.lookup_tool import lookup_workflow_reference
from workflow_engine.lookup_schema import lookup_zuora_schema


def _load_json(path: str | None) -> dict[str, Any]:
    if path and path != "-":
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.loads(sys.stdin.read())


def _cmd_lookup(args: argparse.Namespace) -> int:
    text = lookup_workflow_reference(args.topic, args.subtopic or "")
    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def _cmd_lookup_schema(args: argparse.Namespace) -> int:
    text = lookup_zuora_schema(
        args.object_name,
        include_fields=not args.no_fields,
        include_custom_fields=not args.no_custom_fields,
        include_relationships=args.relationships,
        context_filter=args.context or None,
    )
    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    stage = args.stage
    if stage == "intent":
        payload = _load_json(args.input)
        report = validate_workflow_plan(stage="intent", intent=payload)
    else:
        payload = _load_json(args.input)
        report = validate_workflow_plan(stage="plan", plan=payload)
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if report.get("ok") else 1


def _cmd_build(args: argparse.Namespace) -> int:
    plan = _load_json(args.input)
    result = build_workflow_definition(plan)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if result.get("ok") and result.get("workflow_json"):
            out_path.write_text(json.dumps(result["workflow_json"], indent=2) + "\n", encoding="utf-8")
        meta_path = out_path.with_suffix(out_path.suffix + ".build-result.json")
        meta_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if result.get("ok") else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Zuora workflow engine")
    sub = parser.add_subparsers(dest="command", required=True)

    p_lookup = sub.add_parser("lookup", help="lookup_workflow_reference")
    p_lookup.add_argument("topic", help="topic (events, task, linkage_rules, ...)")
    p_lookup.add_argument("subtopic", nargs="?", default="", help="optional subtopic")
    p_lookup.set_defaults(func=_cmd_lookup)

    p_schema = sub.add_parser("lookup-schema", help="lookup_zuora_schema (live /describe when ZUORA_* set)")
    p_schema.add_argument("object_name", help="Zuora object name, e.g. Invoice")
    p_schema.add_argument("--context", help="Filter fields by describe context (export, soap, …)")
    p_schema.add_argument("--relationships", action="store_true", help="Include related objects")
    p_schema.add_argument("--no-fields", action="store_true", help="Omit field list")
    p_schema.add_argument("--no-custom-fields", action="store_true", help="Omit custom fields")
    p_schema.set_defaults(func=_cmd_lookup_schema)

    p_val = sub.add_parser("validate-plan", help="validate intent or plan JSON")
    p_val.add_argument("--stage", choices=["intent", "plan"], required=True)
    p_val.add_argument("--input", "-i", required=True, help="path to JSON file or '-' for stdin")
    p_val.set_defaults(func=_cmd_validate)

    p_build = sub.add_parser("build", help="build importable workflow JSON from plan")
    p_build.add_argument("--input", "-i", required=True, help="path to plan JSON")
    p_build.add_argument("--output", "-o", help="write workflow JSON to path")
    p_build.set_defaults(func=_cmd_build)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except json.JSONDecodeError as exc:
        print(f"JSON parse error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
