"""CLI-oriented validate_workflow_plan (no Strands runtime)."""

from __future__ import annotations

import json
from typing import Any

from workflow_engine.workflow_reference.intent_validator import validate_intent
from workflow_engine.workflow_reference.plan_validator import validate_plan
from workflow_engine.relationships import build_relationships_graph_for_plan


def validate_workflow_plan(
    *,
    stage: str,
    intent: dict[str, Any] | None = None,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate intent or plan; return structured report dict."""
    stage_norm = (stage or "").lower().strip()

    if stage_norm == "intent":
        if not isinstance(intent, dict):
            return {
                "ok": False,
                "errors": [
                    {
                        "code": "INVALID_INPUT",
                        "message": "stage='intent' requires an intent dict",
                    }
                ],
            }
        return validate_intent(intent)

    if stage_norm == "plan":
        if not isinstance(plan, dict):
            return {
                "ok": False,
                "errors": [
                    {
                        "code": "INVALID_INPUT",
                        "message": "stage='plan' requires a plan dict",
                    }
                ],
            }
        relationships_graph = build_relationships_graph_for_plan(plan)
        return validate_plan(plan, relationships_graph=relationships_graph or None)

    return {
        "ok": False,
        "errors": [
            {
                "code": "INVALID_STAGE",
                "message": f"Unknown stage {stage!r}; use 'intent' or 'plan'",
            }
        ],
    }


def validate_workflow_plan_json(
    *,
    stage: str,
    intent: dict[str, Any] | None = None,
    plan: dict[str, Any] | None = None,
) -> str:
    """Validate and return JSON string (for CLI)."""
    report = validate_workflow_plan(stage=stage, intent=intent, plan=plan)
    return json.dumps(report, indent=2)
