"""CLI-oriented build_workflow_definition (no Strands / LLM sub-agents)."""

from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from typing import Any

from workflow_engine.build_support import (
    _auto_populate_query_fields,
    _validate_and_filter_task_fields,
    _validate_json_schema,
    _validate_pre_import,
    analyze_plan_for_optimizations,
)
from workflow_engine.content_render import render_callout_body_from_brief
from workflow_engine.relationships import build_relationships_graph_async, build_relationships_graph_sync
from workflow_engine.workflow_reference.assembler import assemble_workflow as _assemble_workflow
from workflow_engine.workflow_reference.auto_tags import apply_auto_tags
from workflow_engine.workflow_reference.content_templates import (
    _looks_like_html,
    wrap_text_in_html_shell,
)
from workflow_engine.workflow_reference.data_flow import DataFlowTracker
from workflow_engine.workflow_reference.event_parameters import seed_event_data_paths
from workflow_engine.workflow_reference.plan_normalizer import normalize_plan
from workflow_engine.workflow_reference.plan_validator import validate_plan
from workflow_engine.workflow_reference.task_templates import TaskTemplateEngine
from workflow_engine.zuora_http import session_from_env

_TEMPLATE_ENGINE = TaskTemplateEngine()

_PLAN_ONLY_EMAIL_KEYS = ("intent", "data_vars", "tone", "cta", "audience")
_PLAN_ONLY_CALLOUT_KEYS = ("body_brief", "body_vars")
_MUTATING_HTTP_METHODS = frozenset({"POST", "PUT", "PATCH"})


def _finalize_wire_json(workflow_json: dict[str, Any]) -> None:
    """Apply coding-agent wire-format fixes expected by lint-workflow-json.js."""
    wf = workflow_json.get("workflow")
    if isinstance(wf, dict):
        wf.setdefault("id", 1)
        wf.pop("ui_trigger", None)


def _finalize_email_content_stub(tasks: list[dict[str, Any]], *, workflow_name: str) -> list[str]:
    """Wrap email briefs in HTML shell — no creative sub-agent in v1."""
    warnings: list[str] = []
    for task in tasks:
        if task.get("action_type") != "Email":
            continue
        params = task.get("parameters") or {}
        email = params.get("email")
        if not isinstance(email, dict):
            continue
        task_name = task.get("name", "") or f"task-{task.get('id', '?')}"
        template_raw = str(email.get("template") or "").strip()
        intent = str(email.get("intent") or "").strip()
        subject = str(email.get("subject") or "Notification").strip()
        if template_raw and _looks_like_html(template_raw):
            pass
        elif intent or template_raw:
            email["template"] = wrap_text_in_html_shell(
                intent or template_raw,
                subject=subject,
                workflow_name=workflow_name,
            )
            if intent:
                warnings.append(
                    f"Email task '{task_name}': used HTML shell stub (no creative renderer in coding-agent engine)."
                )
        else:
            warnings.append(f"Email task '{task_name}': no template/intent; emitted generic shell.")
            email["template"] = wrap_text_in_html_shell("", subject=subject, workflow_name=workflow_name)
        for key in _PLAN_ONLY_EMAIL_KEYS:
            email.pop(key, None)
    return warnings


def _finalize_callout_bodies(
    tasks: list[dict[str, Any]],
    *,
    workflow_name: str,
) -> tuple[list[str], list[str]]:
    """Expand ``body_brief`` deterministically or require ``raw_body``."""
    warnings: list[str] = []
    errors: list[str] = []
    for task in tasks:
        action_type = task.get("action_type", "")
        if action_type not in ("Callout", "AsynchronousCallout"):
            continue
        params = task.get("parameters") or {}
        if not isinstance(params, dict):
            continue
        task_name = task.get("name", "") or f"task-{task.get('id', '?')}"
        method = str(params.get("method") or "POST").strip().upper()
        url = str(params.get("url") or "").strip()
        raw_body = str(params.get("raw_body") or "").strip()
        body_brief = str(params.get("body_brief") or "").strip()
        body_vars = params.get("body_vars") or []
        if not isinstance(body_vars, list):
            body_vars = [body_vars]

        if method not in _MUTATING_HTTP_METHODS:
            for key in _PLAN_ONLY_CALLOUT_KEYS:
                params.pop(key, None)
            continue

        if raw_body:
            if not raw_body.startswith(("{", "[")):
                warnings.append(
                    f"Callout task '{task_name}': raw_body does not begin with '{{' or '['."
                )
        elif body_brief:
            params["raw_body"] = render_callout_body_from_brief(
                url=url,
                method=method,
                body_brief=body_brief,
                body_vars=body_vars,
                workflow_name=workflow_name,
                task_name=task_name,
            )
            warnings.append(
                f"Callout task '{task_name}': expanded body_brief into raw_body via deterministic renderer."
            )
        else:
            errors.append(
                f"Callout task '{task_name}': mutating Callout requires raw_body or body_brief + body_vars."
            )

        for key in _PLAN_ONLY_CALLOUT_KEYS:
            params.pop(key, None)
    return warnings, errors


async def _build_workflow_async(plan_data: dict[str, Any]) -> dict[str, Any]:
    session = session_from_env()
    relationships_graph = await build_relationships_graph_async(plan_data, tool_context=session)
    if not relationships_graph:
        relationships_graph = build_relationships_graph_sync(plan_data)

    pv_report = validate_plan(plan_data, relationships_graph=relationships_graph or None)
    if not pv_report["ok"]:
        return {
            "ok": False,
            "workflow_json": None,
            "errors": [
                f"{e.get('code', 'ERROR')} at {e.get('path', '')}: {e.get('message', '')}"
                for e in (pv_report.get("errors") or [])
                if isinstance(e, dict)
            ],
            "warnings": [],
            "plan_validation": pv_report,
        }

    query_info = _auto_populate_query_fields(plan_data.get("tasks") or [])

    field_warnings, field_errors = await _validate_and_filter_task_fields(
        plan_data.get("tasks") or [],
        tool_context=session,
        relationships_graph=relationships_graph,
    )
    if field_errors:
        return {
            "ok": False,
            "workflow_json": None,
            "errors": field_errors,
            "warnings": field_warnings + query_info,
            "plan_validation": pv_report,
        }

    callout_warnings, callout_errors = _finalize_callout_bodies(
        plan_data.get("tasks") or [],
        workflow_name=str(plan_data.get("name") or ""),
    )
    if callout_errors:
        return {
            "ok": False,
            "workflow_json": None,
            "errors": callout_errors,
            "warnings": callout_warnings,
            "plan_validation": pv_report,
        }

    apply_auto_tags(plan_data)
    email_warnings = _finalize_email_content_stub(
        plan_data.get("tasks") or [],
        workflow_name=str(plan_data.get("name") or ""),
    )

    assembled_json, assembly_errors, assembly_warnings = _assemble_workflow(plan_data, _TEMPLATE_ENGINE)
    if assembly_errors:
        return {
            "ok": False,
            "workflow_json": None,
            "errors": assembly_errors,
            "warnings": assembly_warnings + callout_warnings + email_warnings,
            "plan_validation": pv_report,
        }

    _finalize_wire_json(assembled_json)

    schema_errors = _validate_json_schema(assembled_json)
    if schema_errors:
        return {
            "ok": False,
            "workflow_json": None,
            "errors": schema_errors,
            "warnings": assembly_warnings + callout_warnings + email_warnings,
            "plan_validation": pv_report,
        }

    pre_import_errors, pre_import_warnings = _validate_pre_import(assembled_json)
    if pre_import_errors:
        return {
            "ok": False,
            "workflow_json": None,
            "errors": pre_import_errors,
            "warnings": pre_import_warnings + assembly_warnings + callout_warnings + email_warnings,
            "plan_validation": pv_report,
        }

    tracker = DataFlowTracker()
    trigger = plan_data.get("trigger") or {}
    tracker.available |= seed_event_data_paths(trigger.get("event_names") or [])
    tracker.add_input_fields(plan_data.get("input_fields") or [])
    trace: list[dict[str, Any]] = [
        {
            "after_task_id": 0,
            "task_name": "Workflow Start",
            "available_data": tracker.get_available(),
        }
    ]
    for task in plan_data.get("tasks") or []:
        tid = task.get("id")
        tracker.after_task(
            task.get("action_type", ""),
            {
                **(task.get("parameters") or {}),
                "id": tid,
                "object": task.get("object", ""),
                "placement": (task.get("parameters") or {}).get("placement", ""),
            },
            task.get("name", ""),
        )
        trace.append(
            {
                "after_task_id": tid,
                "task_name": task.get("name", ""),
                "available_data": tracker.get_available(),
            }
        )

    suggestions = analyze_plan_for_optimizations(
        plan_data.get("tasks") or [],
        plan_data.get("linkages") or [],
    )

    all_warnings = (
        assembly_warnings
        + pre_import_warnings
        + callout_warnings
        + email_warnings
        + query_info
        + field_warnings
        + [
            f"{w.get('code', 'WARN')} at {w.get('path', '')}: {w.get('message', '')}"
            for w in (pv_report.get("warnings") or [])
            if isinstance(w, dict)
        ]
    )

    return {
        "ok": True,
        "workflow_json": assembled_json,
        "errors": [],
        "warnings": all_warnings,
        "plan_validation": pv_report,
        "data_trace": trace,
        "suggestions": suggestions,
        "schema_source": "api" if session is not None else "cached",
    }


def build_workflow_definition(plan: dict[str, Any]) -> dict[str, Any]:
    """Assemble importable workflow JSON from a WorkflowPlan."""
    if not isinstance(plan, dict):
        return {
            "ok": False,
            "workflow_json": None,
            "errors": ["plan must be a JSON object (WorkflowPlan dict)"],
            "warnings": [],
        }

    plan_data = deepcopy(plan)
    normalize_plan(plan_data)
    return asyncio.run(_build_workflow_async(plan_data))


def build_workflow_definition_json(plan: dict[str, Any]) -> str:
    """Build and return JSON result string (for CLI)."""
    result = build_workflow_definition(plan)
    return json.dumps(result, indent=2)
