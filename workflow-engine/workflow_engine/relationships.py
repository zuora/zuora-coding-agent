"""Relationship graph helpers for plan validation and build."""

from __future__ import annotations

import asyncio
from typing import Any

from workflow_engine.workflow_reference.event_parameters import coerce_event_names_list
from workflow_engine.workflow_reference.reference_lookup import load_object_relationships
from workflow_engine.zuora_http import session_from_env


def collect_object_names_from_plan(plan: dict[str, Any]) -> set[str]:
    """Collect Zuora object names referenced in a WorkflowPlan."""
    names: set[str] = set()
    trigger = plan.get("trigger") or {}
    for event in coerce_event_names_list(trigger.get("event_names")):
        names.add(event)
    for task in plan.get("tasks") or []:
        if not isinstance(task, dict):
            continue
        obj = task.get("object")
        if isinstance(obj, str) and obj and not obj.endswith(".csv"):
            names.add(obj)
        params = task.get("parameters") or {}
        if isinstance(params, dict):
            fields = params.get("fields")
            if isinstance(fields, dict):
                names.update(k for k in fields if isinstance(k, str) and k[0].isupper())
            entity = params.get("entity_name")
            if isinstance(entity, str) and entity:
                names.add(entity)
    return names


def build_relationships_graph_sync(plan: dict[str, Any]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Return legacy relationships graph shape from bundled markdown."""
    graph = load_object_relationships()
    if not graph:
        return {}
    referenced = collect_object_names_from_plan(plan)
    if not referenced:
        return graph
    return graph


async def build_relationships_graph_async(
    plan: dict[str, Any],
    *,
    tool_context: Any = None,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Resolve relationships via live/cached describe when credentials are available."""
    from workflow_engine.workflow_reference.object_metadata import build_relationships_graph

    session = tool_context or session_from_env()
    if session is not None:
        try:
            graph = await build_relationships_graph(plan, session)
            if graph:
                return graph
        except Exception:
            pass
    return build_relationships_graph_sync(plan)


def build_relationships_graph_for_plan(
    plan: dict[str, Any],
    *,
    tool_context: Any = None,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Sync entry point: live graph when ``ZUORA_*`` env vars are set, else static."""
    session = tool_context or session_from_env()
    if session is not None:
        return asyncio.run(build_relationships_graph_async(plan, tool_context=session))
    return build_relationships_graph_sync(plan)
