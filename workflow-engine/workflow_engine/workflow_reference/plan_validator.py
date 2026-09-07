"""Deterministic structural plan validator.

Runs pre-assembly checks against a WorkflowPlan dict and returns structured
errors plus fix hints so the LLM can iteratively refine the plan. No LLM calls,
no NL parsing; all checks use Pydantic-introspected task metadata
(``task_registry``), ``VALID_EVENT_NAMES``, ``TASK_LINKAGE_TYPES``,
``DataFlowTracker``, and the KB relationships.

Plan-time validation is intentionally more lenient than export-time: briefs
may stand in for ``template`` / ``raw_body``, and object/object_id coverage is
checked here rather than via strict ``TASK_TYPE_CONFIG_MAP`` model_validate
(that strict pass runs in ``validate_workflow_export_strict``).

Target latency: <50ms for typical plans.
"""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

from pydantic import ValidationError

from workflow_engine.workflow_reference.data_flow import DataFlowTracker
from workflow_engine.workflow_reference.event_parameters import (
    EVENT_BASE_OBJECTS,
    EVENT_PAYLOAD_OBJECTS,
    RUN_EVENTS,
    VALID_EVENT_NAMES,
    generate_event_parameters,
    seed_event_data_paths,
    suggest_event_name,
)
from workflow_engine.workflow_reference.models import TASK_LINKAGE_TYPES as VALID_LINKAGES
from workflow_engine.workflow_reference.models import (
    TASK_TYPE_CONFIG_MAP,
    TASK_TYPE_TASK_MAP,
    TaskTypeEnum,
    WorkflowPlan,
)
from workflow_engine.workflow_reference.plan_normalizer import normalize_plan

# ---------------------------------------------------------------------------
# Reference data derived from generated Pydantic models
# ---------------------------------------------------------------------------

TASK_TYPES: frozenset[str] = frozenset(e.value for e in TaskTypeEnum)

# Common pass-through parameters that every task accepts (mirrored from
# ``models.plan._COMMON_PASS_THROUGH``) plus the creative-brief keys that stand
# in for ``template`` / ``raw_body`` at plan time.
_COMMON_PASS_THROUGH: frozenset[str] = frozenset(
    {
        "strict_variables",
        "disable_validation",
        "delete_payload_paths",
        "intent",
        "data_vars",
        "body_brief",
        "body_vars",
        "tone",
        "cta",
    }
)


def _task_requires_top(action: str, field: str) -> bool:
    """Return True when the generated ``*Task`` class declares ``field``
    as a required root-level property (e.g. ``object``, ``object_id``).
    """
    task_cls = TASK_TYPE_TASK_MAP.get(action)
    if task_cls is None:
        return False
    fld = task_cls.model_fields.get(field)
    return bool(fld and fld.is_required())


def _allowed_params(action: str) -> set[str]:
    """Return the set of parameter names declared on ``<Action>TaskParameters``."""
    cfg = TASK_TYPE_CONFIG_MAP.get(action)
    if cfg is None:
        return set()
    return set(cfg.model_fields.keys())


# VALID_LINKAGES is sourced from models.TASK_LINKAGE_TYPES (generated from the
# manifest by build_models.py). It is re-exported under the legacy name for
# backward compatibility with callers that still import it from here.
# A value of None indicates dynamic linkages (e.g., Logic::Case with
# Case_1..Case_N + Case_Else).

# Tasks whose output is a collection that Iterate can walk.
_ITERATE_SUPPORTED_SOURCES: frozenset[str] = frozenset(
    {
        "Export",
        "Query",
        "Data::Aqua",
        "Data::Link",
        "GraphQuery",
        "CustomObject::Query",
    }
)

# Tasks that produce files (Iterate over a file-producing source requires the
# object to reference the file by name ending in .csv[.zip]).
_FILE_PRODUCING: frozenset[str] = frozenset(
    {
        "Export",
        "Data::Aqua",
        "Data::Link",
    }
)


def _load_fk_fields_by_object() -> dict[str, dict[str, str]]:
    """Parse relationships KB into ``{ParentObject: {ChildObject: FK_field}}`` map.

    Example entry::

        {"Invoice": {"InvoiceItem": "InvoiceId", "CreditMemoItem": "InvoiceId"}}

    The mapping is inferred from "References (foreign keys / relations)" sections
    using lines like ``- InvoiceId -> Invoice``.
    """
    kb_path = (
        Path(__file__).resolve().parents[2] / "knowledge_base" / "zuora_objects_relationships.md"
    )
    if not kb_path.exists():
        return {}

    fk_map: dict[str, dict[str, str]] = {}
    current_child: Optional[str] = None
    in_references = False
    for raw_line in kb_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("## ") and len(line) > 3:
            current_child = line[3:].strip()
            in_references = False
            continue
        if line.startswith("**References"):
            in_references = True
            continue
        if line.startswith("**Referenced"):
            in_references = False
            continue
        if not in_references or not current_child or not line.startswith("- "):
            continue
        # Patterns: "- InvoiceId -> Invoice" or "- Invoice -> Invoice (object)"
        m = re.match(r"-\s*([A-Za-z][\w]*?)\s*->\s*([A-Za-z][\w]*)", line)
        if not m:
            continue
        field_name, parent = m.group(1), m.group(2)
        if not field_name.endswith("Id"):
            continue
        parent_canonical = parent[:1].upper() + parent[1:]
        fk_map.setdefault(parent_canonical, {})[current_child] = field_name
    return fk_map


_FK_FIELDS = _load_fk_fields_by_object()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


_WIRE_FORMAT_FIX_HINT = (
    "Your plan is in the Zuora wire/export format (top-level `workflow` key with "
    "`event_trigger`/`scheduled_trigger`/`callout_trigger` booleans and "
    "`event_triggers[]`). That is the OUTPUT of `build_workflow_definition`, not "
    "the INPUT to `validate_workflow_plan`. Use the flat plan shape with "
    "top-level `name`, `description`, `call_type`, `trigger: {type, event_names}`, "
    "`tasks[]`, and `linkages[]`. Example for an event trigger: "
    '`{"name": "...", "description": "...", "call_type": "BATCH", '
    '"trigger": {"type": "event", "event_names": ["BillingRunCompletion"]}, '
    '"tasks": [...], "linkages": [...]}`.'
)


def _detect_wire_format_shape(plan: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Detect the Zuora wire/export shape and return a structured error.

    The wire shape wraps workflow-level fields in a ``workflow`` key and uses
    ``event_trigger`` / ``scheduled_trigger`` / ``callout_trigger`` booleans with
    an ``event_triggers[]`` array. That is what the assembler *produces*, not
    what the plan validator *expects*. We detect this early so the LLM gets one
    clear actionable error instead of four vague "Field required" messages.

    Returns ``None`` when the plan is the correct flat shape.
    """
    # Strong signal: top-level wrapper plus absence of the flat required keys.
    has_wrapper = isinstance(plan.get("workflow"), dict)
    missing_flat_required = (
        not all(plan.get(k) for k in ("name", "description", "call_type")) and "trigger" not in plan
    )

    # Strong signal: wire-format trigger flags/array at top level.
    has_wire_flags = any(
        k in plan for k in ("event_trigger", "scheduled_trigger", "callout_trigger")
    ) or isinstance(plan.get("event_triggers"), list)

    # Weaker signal: wire-format flags nested inside ``workflow``.
    wrapper_has_wire_flags = has_wrapper and any(
        k in plan["workflow"]
        for k in ("event_trigger", "scheduled_trigger", "callout_trigger", "event_triggers")
    )

    if (has_wrapper and missing_flat_required) or has_wire_flags or wrapper_has_wire_flags:
        return {
            "path": "plan",
            "code": "WIRE_FORMAT_SHAPE",
            "message": (
                "Plan appears to be in the Zuora wire/export format, not the "
                "WorkflowPlan (plan) format."
            ),
            "fix_hint": _WIRE_FORMAT_FIX_HINT,
        }
    return None


def validate_plan(
    plan_data: dict[str, Any],
    *,
    relationships_graph: Optional[dict[str, dict[str, list[dict[str, Any]]]]] = None,
) -> dict[str, Any]:
    """Validate a plan dict pre-assembly.

    Returns ``{ok, errors, warnings, data_trace, corrections}``. ``ok`` is True
    only when there are no errors (warnings are non-fatal).

    Errors include a ``code`` and ``fix_hint`` where applicable so the LLM can
    auto-correct and re-validate.

    Args:
        plan_data: The WorkflowPlan dict.
        relationships_graph: Optional resolver-backed graph
            (``object_metadata.build_relationships_graph``).  When provided it
            overrides the markdown fallback used for FK / cardinality checks.
    """
    result: dict[str, Any] = {
        "ok": True,
        "errors": [],
        "warnings": [],
        "corrections": [],
        "data_trace": [],
    }

    if not isinstance(plan_data, dict):
        result["ok"] = False
        result["errors"].append(
            {
                "path": "plan",
                "code": "INVALID_TYPE",
                "message": "plan must be a JSON object",
                "fix_hint": "Pass the plan as a JSON object with name, trigger, tasks, linkages.",
            }
        )
        return result

    # Detect the Zuora wire/export shape (top-level `workflow` wrapper with
    # `event_trigger` booleans) and emit one clear error instead of four
    # vague "Field required" messages from Pydantic.
    wire_shape_err = _detect_wire_format_shape(plan_data)
    if wire_shape_err is not None:
        result["ok"] = False
        result["errors"].append(wire_shape_err)
        return result

    # Normalize LLM-friendly shapes (fields arrays, flat email, etc.) before
    # any downstream checks. Uses deepcopy so the caller's plan is untouched
    # unless they explicitly want mutations via validate_plan_in_place.
    plan_data = deepcopy(plan_data)
    normalize_plan(plan_data)

    _validate_pydantic(plan_data, result)
    if result["errors"]:
        result["ok"] = False
        return result

    fk_fields = _fk_fields_from_graph(relationships_graph) if relationships_graph else None

    _validate_trigger_call_type(plan_data, result)
    _validate_task_types_and_params(plan_data, result)
    _validate_linkages(plan_data, result)
    _validate_iterate_sources(plan_data, result)
    _validate_fk_fields(plan_data, result, fk_fields=fk_fields)
    _validate_data_flow(plan_data, result)
    _validate_data_gathering_efficiency(
        plan_data,
        result,
        relationships_graph=relationships_graph,
    )
    _validate_content_briefs(plan_data, result)

    result["ok"] = not result["errors"]
    return result


def _fk_fields_from_graph(
    graph: dict[str, dict[str, list[dict[str, Any]]]],
) -> dict[str, dict[str, str]]:
    """Convert a resolver relationships graph into the legacy FK map shape.

    Returned shape: ``{Parent: {Child: FK_field}}``.
    """
    fk_map: dict[str, dict[str, str]] = {}
    for child, rel in graph.items():
        child_canonical = child[:1].upper() + child[1:] if child else child
        for ref in rel.get("references") or []:
            field = ref.get("field")
            parent = ref.get("target_object")
            if not field or not parent or not field.endswith(("Id", "ID")):
                continue
            parent_canonical = parent[:1].upper() + parent[1:]
            fk_map.setdefault(parent_canonical, {})[child_canonical] = field
    return fk_map


# ---------------------------------------------------------------------------
# Check 1: Pydantic structural
# ---------------------------------------------------------------------------


def _validate_pydantic(plan: dict[str, Any], result: dict[str, Any]) -> None:
    """Run the structural ``WorkflowPlan`` model validation.

    The generated ``*Parameters`` models accept dicts/lists where the schema
    types them as objects/arrays (e.g. ``Query.fields`` is ``dict``;
    ``Callout.headers`` is ``list[{key, value}]``), so the normalizer's output
    can be fed in directly — no wire-format JSON stringification here. That
    transformation is the responsibility of ``TaskTemplateEngine`` at export
    time (Phase 5b).
    """
    try:
        WorkflowPlan.model_validate(plan)
    except ValidationError as e:
        for err in e.errors():
            path = ".".join(str(p) for p in err["loc"])
            msg = err["msg"]
            result["errors"].append(
                {
                    "path": path,
                    "code": err.get("type", "VALIDATION_ERROR").upper(),
                    "message": msg,
                    "fix_hint": _pydantic_fix_hint(path, msg, err.get("type", "")),
                }
            )
    except Exception as e:
        result["errors"].append(
            {
                "path": "plan",
                "code": "PARSE_ERROR",
                "message": str(e),
                "fix_hint": "Check the plan JSON for syntax errors.",
            }
        )


def _pydantic_fix_hint(path: str, msg: str, err_type: str) -> str:
    lower = msg.lower()
    if "action_type" in path and "not a valid" in lower:
        return (
            "Invalid task type. Check the spelling (case-sensitive, e.g. "
            "'Logic::Case' not 'LogicCase')."
        )
    if err_type == "missing" or "missing" in lower:
        return f"Required field `{path}` is missing. Add it to the plan JSON."
    if "fields" in path and ("type" in lower or "str type" in lower):
        return (
            "Query/Export fields must be "
            '{"ObjectName": {"FieldName": "true"}} or {"ObjectName": ["FieldName"]}.'
        )
    if "linkage" in path.lower():
        return (
            "Each linkage needs 'from', 'to', and 'type'. 'from' is either "
            "'workflow_start' or a task id (int)."
        )
    if "trigger" in path.lower():
        return "trigger.type must be one of: ondemand, scheduled, event, callout."
    return f"Fix `{path}`: {msg}"


# ---------------------------------------------------------------------------
# Check 2: Event name + call_type consistency
# ---------------------------------------------------------------------------


def _validate_trigger_call_type(plan: dict[str, Any], result: dict[str, Any]) -> None:
    trigger = plan.get("trigger") or {}
    ttype = trigger.get("type")
    call_type = plan.get("call_type")

    if ttype == "event":
        event_names = trigger.get("event_names") or []
        for i, name in enumerate(event_names):
            if name in EVENT_BASE_OBJECTS:
                continue
            suggestion = suggest_event_name(name)
            if suggestion:
                result["corrections"].append(
                    {
                        "path": f"trigger.event_names[{i}]",
                        "from": name,
                        "to": suggestion,
                        "reason": "Fuzzy-matched to valid event",
                    }
                )
                event_names[i] = suggestion
            else:
                result["errors"].append(
                    {
                        "path": f"trigger.event_names[{i}]",
                        "code": "UNKNOWN_EVENT_NAME",
                        "message": f"{name!r} is not a valid Zuora event.",
                        "fix_hint": (
                            f"Use one of: {', '.join(VALID_EVENT_NAMES[:8])}... "
                            "(see lookup_workflow_reference(topic='events'))."
                        ),
                    }
                )

        has_run = any(n in RUN_EVENTS for n in event_names)
        if has_run and call_type not in ("BATCH", "ASYNC"):
            result["warnings"].append(
                {
                    "path": "call_type",
                    "code": "CALL_TYPE_MISMATCH",
                    "message": (
                        f"Run-completion events ({', '.join(n for n in event_names if n in RUN_EVENTS)}) "
                        f"produce large datasets and should use call_type=BATCH; got {call_type!r}."
                    ),
                    "fix_hint": "Set call_type='BATCH' when triggering on run-completion events.",
                }
            )
        elif event_names and not has_run and call_type not in ("REALTIME", "ASYNC"):
            result["warnings"].append(
                {
                    "path": "call_type",
                    "code": "CALL_TYPE_MISMATCH",
                    "message": (
                        f"Per-record events should use call_type=REALTIME; got {call_type!r}."
                    ),
                    "fix_hint": "Set call_type='REALTIME' for per-record event triggers.",
                }
            )

    elif ttype == "scheduled":
        if call_type not in ("ASYNC", "BATCH"):
            result["warnings"].append(
                {
                    "path": "call_type",
                    "code": "CALL_TYPE_MISMATCH",
                    "message": (
                        f"Scheduled workflows should use call_type=ASYNC (or BATCH for heavy jobs); "
                        f"got {call_type!r}."
                    ),
                    "fix_hint": "Set call_type='ASYNC' for scheduled workflows.",
                }
            )


# ---------------------------------------------------------------------------
# Check 3: Task types + required/unknown params
# ---------------------------------------------------------------------------


def _validate_task_types_and_params(plan: dict[str, Any], result: dict[str, Any]) -> None:
    """Shape-level task checks backed by Pydantic model introspection.

    Derives:
      - valid task types from ``TaskTypeEnum``
      - required root-level fields (``object``, ``object_id``) from
        ``TASK_TYPE_TASK_MAP[action].model_fields[...].is_required()``
      - allowed parameter names from ``TASK_TYPE_CONFIG_MAP[action].model_fields``

    Required *parameters* (e.g. ``Query.fields``) are intentionally NOT
    blocked here — that's the export-time strict pass. At plan time a brief
    or placeholder is acceptable.
    """
    tasks = plan.get("tasks") or []

    for i, task in enumerate(tasks):
        action = task.get("action_type")
        if action not in TASK_TYPES:
            result["errors"].append(
                {
                    "path": f"tasks[{i}].action_type",
                    "code": "UNKNOWN_TASK_TYPE",
                    "message": f"{action!r} is not a known task type.",
                    "fix_hint": (
                        "See lookup_workflow_reference(topic='task_types') for the "
                        "full catalog of valid task types."
                    ),
                }
            )
            continue

        if _task_requires_top(action, "object") and not task.get("object"):
            result["errors"].append(
                {
                    "path": f"tasks[{i}].object",
                    "code": "MISSING_REQUIRED_TOP_LEVEL",
                    "message": f"Task type {action!r} requires `object`.",
                    "fix_hint": (
                        "Set the `object` field on the task (e.g., 'Invoice', 'Account')."
                    ),
                }
            )
        if _task_requires_top(action, "object_id") and not task.get("object_id"):
            result["errors"].append(
                {
                    "path": f"tasks[{i}].object_id",
                    "code": "MISSING_REQUIRED_TOP_LEVEL",
                    "message": f"Task type {action!r} requires `object_id`.",
                    "fix_hint": (
                        "Set `object_id` to the target record's id (Liquid Data.* reference "
                        "is fine, e.g., '{{Data.Invoice.Id}}')."
                    ),
                }
            )

        params = task.get("parameters") or {}
        allowed_params = _allowed_params(action)
        unknown = [
            p for p in params.keys() if p not in allowed_params and p not in _COMMON_PASS_THROUGH
        ]
        if unknown:
            result["warnings"].append(
                {
                    "path": f"tasks[{i}].parameters",
                    "code": "UNKNOWN_PARAMETER",
                    "message": (
                        f"Task {action!r} received unknown parameters: {unknown}. "
                        f"Allowed: {sorted(allowed_params)[:10]}..."
                    ),
                    "fix_hint": (
                        "Remove the unknown parameters or check "
                        f"lookup_workflow_reference(topic='task', subtopic='{action}')."
                    ),
                }
            )


# ---------------------------------------------------------------------------
# Check 4: Linkage rules (source + target)
# ---------------------------------------------------------------------------


def iterate_body_map(
    linkages: list[dict[str, Any]],
    task_by_id: dict[int, dict[str, Any]],
) -> dict[int, set[int]]:
    """Return ``{iterate_id: set_of_task_ids_inside_its_loop_body}``.

    The body of an Iterate is every task transitively reachable from that
    Iterate's ``For Each`` edge, following any outgoing linkage, and stopping
    at the Iterate itself (so we don't recurse through back-edges).

    Used to distinguish a legitimate entry edge into an Iterate (source is
    outside the loop body) from an illegal back-edge that would re-enter the
    loop indefinitely (source is inside the body).

    Public helper: also consumed by ``assembler.generate_linkages`` so both
    plan validation and assembly share one source of truth for the "is this
    an infinite-loop back-edge?" question.
    """
    out_by_src: dict[int, list[dict[str, Any]]] = {}
    for lnk in linkages:
        s = lnk.get("from")
        if isinstance(s, int):
            out_by_src.setdefault(s, []).append(lnk)

    body_by_iterate: dict[int, set[int]] = {}
    for iter_id, task in task_by_id.items():
        if task.get("action_type") != "Iterate":
            continue
        body: set[int] = set()
        seeds = [
            lnk.get("to")
            for lnk in out_by_src.get(iter_id, [])
            if lnk.get("type") == "For Each" and isinstance(lnk.get("to"), int)
        ]
        stack: list[int] = [s for s in seeds if s is not None]
        while stack:
            cur = stack.pop()
            if cur in body or cur == iter_id:
                continue
            body.add(cur)
            for lnk in out_by_src.get(cur, []):
                nxt = lnk.get("to")
                if isinstance(nxt, int) and nxt != iter_id and nxt not in body:
                    stack.append(nxt)
        body_by_iterate[iter_id] = body
    return body_by_iterate


def _validate_linkages(plan: dict[str, Any], result: dict[str, Any]) -> None:
    tasks = plan.get("tasks") or []
    linkages = plan.get("linkages") or []
    task_by_id: dict[int, dict[str, Any]] = {
        t["id"]: t for t in tasks if isinstance(t.get("id"), int)
    }
    iterate_bodies = iterate_body_map(linkages, task_by_id)

    for i, lnk in enumerate(linkages):
        src = lnk.get("from")
        tgt = lnk.get("to")
        ltype = lnk.get("type", "")
        path_prefix = f"linkages[{i}]"

        if str(src) == "workflow_start":
            if ltype != "Start":
                trigger = plan.get("trigger") or {}
                ev_names = trigger.get("event_names") or []
                if ltype in ev_names:
                    pass
                else:
                    result["warnings"].append(
                        {
                            "path": f"{path_prefix}.type",
                            "code": "START_LINKAGE_TYPE",
                            "message": (
                                f"Entry linkage from workflow_start should be 'Start' "
                                f"(or an event name for event triggers); got {ltype!r}."
                            ),
                            "fix_hint": "Set linkage.type to 'Start' for workflow_start edges.",
                        }
                    )
            continue

        if not isinstance(src, int) or src not in task_by_id:
            continue
        src_type = task_by_id[src].get("action_type", "")
        valid = VALID_LINKAGES.get(src_type)
        if valid is not None and not ltype.startswith("Case_") and ltype not in valid:
            result["errors"].append(
                {
                    "path": f"{path_prefix}.type",
                    "code": "INVALID_LINKAGE_TYPE",
                    "message": (
                        f"Linkage type {ltype!r} is not valid from {src_type!r}. " f"Valid: {valid}"
                    ),
                    "fix_hint": (f"Use one of {valid} for linkages sourced from {src_type!r}."),
                }
            )

        if isinstance(tgt, int) and tgt in task_by_id:
            tgt_type = task_by_id[tgt].get("action_type", "")
            # Back-edge detection: an edge targeting an Iterate with
            # Success/Failure is only illegal when the SOURCE is inside that
            # Iterate's loop body. Entry edges from outside the body are
            # legitimate (e.g. Export(Success) -> Iterate).
            if (
                tgt_type == "Iterate"
                and ltype in ("Success", "Failure")
                and src in iterate_bodies.get(tgt, set())
            ):
                result["errors"].append(
                    {
                        "path": f"{path_prefix}",
                        "code": "ITERATE_BACK_EDGE",
                        "message": (
                            f"Task {src} is inside Iterate {tgt}'s loop body and cannot "
                            f"link back to it with {ltype!r}; that would re-enter the "
                            "loop on every iteration and run forever."
                        ),
                        "fix_hint": (
                            "Remove this edge. Tasks on the 'For Each' branch return "
                            "to the Iterate automatically at the end of each iteration. "
                            "Use Iterate's 'Complete' edge for after-loop tasks, or "
                            "terminate this branch without an edge to continue with "
                            "the next iteration."
                        ),
                    }
                )
            if ltype == "For Each" and src_type != "Iterate":
                result["errors"].append(
                    {
                        "path": f"{path_prefix}.type",
                        "code": "INVALID_LINKAGE_TYPE",
                        "message": "'For Each' linkages are only valid from Iterate tasks.",
                        "fix_hint": (
                            "Change the source to an Iterate task, or use 'Success' instead."
                        ),
                    }
                )


# ---------------------------------------------------------------------------
# Check 5: Iterate source reference
# ---------------------------------------------------------------------------


def _validate_iterate_sources(plan: dict[str, Any], result: dict[str, Any]) -> None:
    tasks = plan.get("tasks") or []
    by_id = {t["id"]: t for t in tasks if isinstance(t.get("id"), int)}
    linkages = plan.get("linkages") or []

    predecessors: dict[int, list[int]] = {}
    for lnk in linkages:
        src, tgt = lnk.get("from"), lnk.get("to")
        if isinstance(src, int) and isinstance(tgt, int):
            predecessors.setdefault(tgt, []).append(src)

    for i, task in enumerate(tasks):
        if task.get("action_type") != "Iterate":
            continue
        iter_obj = task.get("object") or (task.get("parameters") or {}).get("object")
        if not iter_obj:
            result["errors"].append(
                {
                    "path": f"tasks[{i}].object",
                    "code": "ITERATE_MISSING_SOURCE",
                    "message": "Iterate task needs an `object` referencing a preceding collection source.",
                    "fix_hint": (
                        "Set object to the predecessor output name (e.g., 'Export.Invoice.csv', "
                        "'Query.Invoice', or a Liquid array reference)."
                    ),
                }
            )
            continue

        preds = [by_id.get(p) for p in predecessors.get(task["id"], []) if p in by_id]
        preds_supported = [
            p for p in preds if p and p.get("action_type") in _ITERATE_SUPPORTED_SOURCES
        ]

        if preds and not preds_supported:
            result["warnings"].append(
                {
                    "path": f"tasks[{i}]",
                    "code": "ITERATE_UNSUPPORTED_SOURCE",
                    "message": (
                        "Iterate's immediate predecessor is not a collection source "
                        "(Export/Query/GraphQuery/Data::*). Iterate only walks arrays."
                    ),
                    "fix_hint": (
                        "Add a Query/Export/GraphQuery task before Iterate, or use a Liquid "
                        "reference that resolves to an array."
                    ),
                }
            )

        # if preds_file_producers and isinstance(iter_obj, str):
        #     if not re.search(r"\.csv(\.zip)?$", iter_obj):
        #         result["warnings"].append({
        #             "path": f"tasks[{i}].object",
        #             "code": "ITERATE_FILE_NAME",
        #             "message": (
        #                 f"Iterate is fed by a file-producing predecessor "
        #                 f"({preds_file_producers[0].get('action_type')}); the `object` "
        #                 f"reference should end in .csv or .csv.zip (got {iter_obj!r})."
        #             ),
        #             "fix_hint": (
        #                 "Reference the emitted file name, e.g., 'Data.Files[\"Export_Invoice.csv\"]'."
        #             ),
        #         })


# ---------------------------------------------------------------------------
# Check 6: FK for parent-child queries
# ---------------------------------------------------------------------------


def _validate_fk_fields(
    plan: dict[str, Any],
    result: dict[str, Any],
    *,
    fk_fields: Optional[dict[str, dict[str, str]]] = None,
) -> None:
    fk_map = fk_fields if fk_fields is not None else _FK_FIELDS
    if not fk_map:
        return

    tasks = plan.get("tasks") or []
    for i, task in enumerate(tasks):
        action = task.get("action_type")
        if action not in ("Query", "Export"):
            continue
        child_obj = task.get("object") or ""
        params = task.get("parameters") or {}
        where = params.get("where_clause") or params.get("where") or ""
        if not child_obj or not isinstance(where, str):
            continue

        matches = re.findall(r"\{\{Data\.([A-Za-z][\w]*)\.Id\}\}", where)
        for parent in matches:
            parent_canon = parent[:1].upper() + parent[1:]
            child_canon = child_obj[:1].upper() + child_obj[1:]
            fk_map_for_parent = fk_map.get(parent_canon, {})
            expected_fk = fk_map_for_parent.get(child_canon)
            if not expected_fk:
                continue
            # Only check that the FK field name appears in the where clause,
            # not that it matches a specific Liquid variable on the RHS.
            fk_pattern = re.compile(rf"\b{re.escape(expected_fk)}\b", re.IGNORECASE)
            if not fk_pattern.search(where):
                result["warnings"].append(
                    {
                        "path": f"tasks[{i}].parameters.where_clause",
                        "code": "FK_FIELD_MISMATCH",
                        "message": (
                            f"{child_obj}.{expected_fk} is the canonical FK to {parent_canon}; "
                            f"the where_clause references {{{{Data.{parent}.Id}}}} but does not "
                            f"appear to filter on `{expected_fk}`."
                        ),
                        "fix_hint": (
                            f"Use `{expected_fk} = '{{{{Data.{parent}.Id}}}}'` to filter "
                            f"{child_obj} by its parent {parent_canon}."
                        ),
                    }
                )


# ---------------------------------------------------------------------------
# Check 7: Liquid reachability + selected-field coverage
# ---------------------------------------------------------------------------


def _validate_data_flow(plan: dict[str, Any], result: dict[str, Any]) -> None:
    tasks = plan.get("tasks") or []
    trigger = plan.get("trigger") or {}
    event_names = trigger.get("event_names") or []

    tracker = DataFlowTracker()
    tracker.available |= seed_event_data_paths(event_names)
    tracker.add_input_fields(plan.get("input_fields") or [])

    for name in event_names:
        if name not in EVENT_BASE_OBJECTS:
            continue
        ep = generate_event_parameters(name) if name not in EVENT_PAYLOAD_OBJECTS else []
        # Attempt to seed selected_fields from any event_parameters the plan carries
        for entry in trigger.get("event_parameters") or ep:
            if not isinstance(entry, dict):
                continue
            for param in entry.get("params") or []:
                obj = param.get("object")
                key = param.get("key")
                if obj and key:
                    tracker.selected_fields.setdefault(obj, set()).add(key)
                    tracker.available.add(f"Data.{obj}.{key}")

    result["data_trace"].append(
        {
            "task_id": 0,
            "task_name": "Workflow Start",
            "available_after": sorted(tracker.get_available())[:20],
        }
    )

    tasks_by_id = {t.get("id"): t for t in tasks if isinstance(t.get("id"), int)}
    for task in tasks:
        tid = task.get("id")
        errors = tracker.validate_task_config(
            task.get("action_type", ""),
            {
                **(task.get("parameters") or {}),
                "id": tid,
                "object": task.get("object", ""),
            },
            task.get("name", ""),
        )
        for msg in errors:
            code = (
                "LIQUID_FIELD_NOT_SELECTED"
                if "preceding tasks only selected" in msg
                else "LIQUID_UNREACHABLE"
            )
            result["errors"].append(
                {
                    "path": f"tasks[{task.get('id')}]",
                    "code": code,
                    "message": msg,
                    "fix_hint": _liquid_fix_hint(msg, tasks_by_id),
                }
            )

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
        result["data_trace"].append(
            {
                "task_id": tid,
                "task_name": task.get("name", ""),
                "available_after": sorted(tracker.get_available())[:20],
            }
        )


def _liquid_fix_hint(msg: str, tasks_by_id: dict[int, dict[str, Any]]) -> str:
    # Attempt to parse "uses field 'X' on Y but preceding tasks only selected: ..."
    m = re.search(r"uses field '([\w]+)' on (\w+)", msg)
    if m:
        field, obj = m.group(1), m.group(2)
        for task in tasks_by_id.values():
            if task.get("action_type") in ("Query", "Export", "GraphQuery") and (
                task.get("object") == obj or (task.get("parameters") or {}).get("placement") == obj
            ):
                return (
                    f"Add '{field}' to tasks where object={obj} "
                    f"(task id {task.get('id')}).parameters.fields.{obj}."
                )
        return f"Add '{field}' to the preceding Query/Export's fields.{obj} list."
    m2 = re.search(r"'\{\{(Data\.[\w\.]+)\}\}'", msg)
    if m2:
        return (
            f"The reference {m2.group(1)} is not available yet. Add a preceding "
            "Query/Export that produces it, or remove this reference."
        )
    return "Ensure the referenced Data.* path is produced by a preceding task."


# ---------------------------------------------------------------------------
# Check 8: Data-gathering efficiency (warnings, non-blocking)
# ---------------------------------------------------------------------------
# Detects the anti-pattern of running one Query per iteration for a 1:1 / N:1
# related object instead of joining that object onto the upstream Export /
# Query / Data::Link that produced the loop input. Emits structural warnings
# (not errors) so the LLM can see and fix before assembly.


_FETCH_TASK_TYPES: frozenset[str] = frozenset(
    {
        "Query",
        "Export",
        "Data::Link",
        "Data::Aqua",
        "GraphQuery",
        "CustomObject::Query",
    }
)


def _upstream_fetch_task(
    iterate_task: dict[str, Any],
    linkages: list[dict[str, Any]],
    tasks_by_id: dict[int, dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Walk the predecessor edges of an Iterate to find the data-producing
    task (the Export/Query/Data::Link whose output the Iterate walks).
    Returns None if no fetch task is found within a short backward walk."""
    iter_id = iterate_task.get("id")
    if not isinstance(iter_id, int):
        return None
    preds: dict[int, list[int]] = {}
    for lnk in linkages:
        s, t = lnk.get("from"), lnk.get("to")
        if isinstance(s, int) and isinstance(t, int):
            preds.setdefault(t, []).append(s)
    visited: set[int] = set()
    stack: list[int] = list(preds.get(iter_id, []))
    while stack:
        cur = stack.pop()
        if cur in visited:
            continue
        visited.add(cur)
        t = tasks_by_id.get(cur)
        if t is None:
            continue
        if t.get("action_type") in _FETCH_TASK_TYPES:
            return t
        stack.extend(preds.get(cur, []))
    return None


def _object_has_fk_to(
    source_obj: str,
    target_obj: str,
    relationships: dict[str, dict[str, list[dict[str, Any]]]],
) -> Optional[str]:
    """Return the FK field name on ``source_obj`` that points at ``target_obj``
    (e.g., Invoice → Account via AccountId), or None if no such 1:1 / N:1
    relationship exists. One-to-many / many-to-many relationships ARE skipped
    — those are the 1:N case we WANT inside an Iterate loop.

    When multiple matching references exist (some codebases carry both
    ``AccountId -> Account`` and ``Account -> Account (object)``), the
    ``<Target>Id`` form is preferred for clearer error messages.
    """
    refs = (relationships.get(source_obj) or {}).get("references") or []
    candidates: list[str] = []
    for ref in refs:
        if ref.get("target_object") != target_obj:
            continue
        cardinality = (ref.get("cardinality") or "").upper()
        if cardinality in {"TO_MANY", "ONE_TO_MANY", "MANY_TO_MANY"}:
            continue
        label = (ref.get("raw_label") or "").lower()
        if "one-to-many" in label or "many-to-many" in label or "to-many" in label:
            continue
        field = ref.get("field")
        if isinstance(field, str) and field:
            candidates.append(field)
    if not candidates:
        return None
    preferred = f"{target_obj}Id"
    if preferred in candidates:
        return preferred
    return candidates[0]


def _validate_data_gathering_efficiency(
    plan: dict[str, Any],
    result: dict[str, Any],
    *,
    relationships_graph: Optional[dict[str, dict[str, list[dict[str, Any]]]]] = None,
) -> None:
    tasks = plan.get("tasks") or []
    linkages = plan.get("linkages") or []
    tasks_by_id: dict[int, dict[str, Any]] = {
        t["id"]: t for t in tasks if isinstance(t.get("id"), int)
    }
    bodies = iterate_body_map(linkages, tasks_by_id)
    if not bodies:
        return

    if relationships_graph is not None:
        relationships = relationships_graph
    else:
        try:
            from workflow_engine.workflow_reference.reference_lookup import (
                load_object_relationships,
            )

            relationships = load_object_relationships()
        except Exception:
            return
    if not relationships:
        return

    for iter_id, body_ids in bodies.items():
        iter_task = tasks_by_id.get(iter_id) or {}
        iter_obj = iter_task.get("object") or ""
        iter_obj_base = iter_obj.split("__")[0].split(".")[0] if iter_obj else ""
        if not iter_obj_base:
            continue

        upstream = _upstream_fetch_task(iter_task, linkages, tasks_by_id)

        for bid in sorted(body_ids):
            task = tasks_by_id.get(bid) or {}
            if task.get("action_type") not in ("Query", "Export"):
                continue
            query_obj = task.get("object") or ""
            if not query_obj or query_obj == iter_obj_base:
                continue

            fk_field = _object_has_fk_to(iter_obj_base, query_obj, relationships)
            if fk_field is None:
                continue

            upstream_hint = (
                f"task id {upstream.get('id')} ({upstream.get('name', '')})"
                if upstream
                else "the upstream Export/Query feeding the Iterate"
            )
            result["warnings"].append(
                {
                    "path": f"tasks[{bid}]",
                    "code": "INEFFICIENT_PER_ITERATION_QUERY",
                    "message": (
                        f"Task id {bid} runs a {task.get('action_type')} on "
                        f"'{query_obj}' for every iteration of Iterate({iter_obj_base}). "
                        f"{iter_obj_base} has a 1:1/N:1 foreign key "
                        f"'{iter_obj_base}.{fk_field}' → {query_obj}, so this is "
                        "one extra database round-trip per loop item."
                    ),
                    "fix_hint": (
                        f"Remove this task and add the needed {query_obj} fields "
                        f"to {upstream_hint}'s parameters.fields under the "
                        f"'{query_obj}' key, e.g. "
                        f'`parameters.fields.{query_obj} = ["Id", "Name", ...]`. '
                        f"ZOQL follows the FK {iter_obj_base}.{fk_field} and "
                        f"populates Data.{query_obj}.* automatically. Keep "
                        "per-iteration Queries only for true 1:N relationships "
                        "(e.g. child line items)."
                    ),
                }
            )


# ---------------------------------------------------------------------------
# Check: Email / Callout content briefs
# ---------------------------------------------------------------------------

_PLAN_TIME_CONTENT_WARN_CHARS = 800
_MUTATING_HTTP_METHODS = frozenset({"POST", "PUT", "PATCH"})
_PLACEHOLDER_SUBJECTS = frozenset({"", "notification", "tbd", "todo"})


def _validate_content_briefs(plan: dict[str, Any], result: dict[str, Any]) -> None:
    """Enforce the brief-first contract for content-heavy tasks.

    Rules:
      - Email: ``parameters.email`` requires ``subject``, plus either a real
        ``template`` (user-supplied HTML) or an ``intent`` brief that the
        creative sub-agent will expand at build time.
      - Callout / AsynchronousCallout (method in POST/PUT/PATCH): ``parameters``
        requires ``url`` plus either a ``body_brief`` (cheap placeholder at
        plan time) or a fully-rendered ``raw_body``. The main planning
        agent is responsible for expanding the brief into ``raw_body``
        after plan approval — typically via ``lookup_zuora_api_spec`` for
        Zuora endpoints — and before calling ``build_workflow_definition``.
      - Warn when plan-time ``template`` or ``raw_body`` exceeds
        ``_PLAN_TIME_CONTENT_WARN_CHARS`` (authoring full HTML/JSON in the
        plan is expensive; prefer a brief).
    """
    tasks = plan.get("tasks") or []
    for idx, task in enumerate(tasks):
        if not isinstance(task, dict):
            continue
        action_type = task.get("action_type", "")
        name = task.get("name") or f"Task {idx}"
        params = task.get("parameters") or {}
        if not isinstance(params, dict):
            continue

        if action_type == "Email":
            email = params.get("email")
            if not isinstance(email, dict):
                continue
            subject = str(email.get("subject") or "").strip()
            intent = str(email.get("intent") or "").strip()
            template = str(email.get("template") or "").strip()

            if subject.lower() in _PLACEHOLDER_SUBJECTS:
                result["errors"].append(
                    {
                        "path": f"tasks[{idx}].parameters.email.subject",
                        "code": "EMAIL_SUBJECT_REQUIRED",
                        "message": (
                            f"Email task '{name}' is missing a specific subject "
                            f"(found {subject!r})."
                        ),
                        "fix_hint": (
                            "Add a specific `subject` (not 'Notification') — include "
                            "a Liquid identifier where useful, e.g. "
                            "'Payment reminder - Invoice #{{Data.Invoice.InvoiceNumber}}'."
                        ),
                    }
                )
            if not intent and not template:
                result["errors"].append(
                    {
                        "path": f"tasks[{idx}].parameters.email",
                        "code": "EMAIL_BRIEF_REQUIRED",
                        "message": (
                            f"Email task '{name}' has no `intent` brief and no "
                            "`template`. The creative sub-agent needs a brief to "
                            "render the final HTML."
                        ),
                        "fix_hint": (
                            "Add `parameters.email.intent` (one-sentence description "
                            "of the email's purpose) and `parameters.email.data_vars` "
                            "(list of Liquid expressions the body should surface). "
                            "Only set `template` directly when the user supplied HTML."
                        ),
                    }
                )
            if template and len(template) > _PLAN_TIME_CONTENT_WARN_CHARS:
                result["warnings"].append(
                    {
                        "path": f"tasks[{idx}].parameters.email.template",
                        "code": "EMAIL_TEMPLATE_TOO_LARGE",
                        "message": (
                            f"Email task '{name}' carries a {len(template)}-char "
                            "`template` in the plan. Full HTML authoring in the plan "
                            "is expensive."
                        ),
                        "fix_hint": (
                            "Drop `template` and switch to an `intent` + `data_vars` "
                            "brief — the creative sub-agent will render the HTML at "
                            "build time. Only keep a full `template` when the user "
                            "supplied the exact copy."
                        ),
                    }
                )

        elif action_type in ("Callout", "AsynchronousCallout"):
            url = str(params.get("url") or "").strip()
            method = str(params.get("method") or "POST").strip().upper()
            raw_body = str(params.get("raw_body") or "").strip()
            body_brief = str(params.get("body_brief") or "").strip()

            if not url:
                result["errors"].append(
                    {
                        "path": f"tasks[{idx}].parameters.url",
                        "code": "CALLOUT_URL_REQUIRED",
                        "message": f"{action_type} task '{name}' is missing a url.",
                        "fix_hint": (
                            "Set `parameters.url` to the target endpoint, e.g. "
                            "'https://example.com/api/v1/resource'."
                        ),
                    }
                )
            if method in _MUTATING_HTTP_METHODS and not raw_body and not body_brief:
                result["errors"].append(
                    {
                        "path": f"tasks[{idx}].parameters",
                        "code": "CALLOUT_BRIEF_REQUIRED",
                        "message": (
                            f"{action_type} task '{name}' uses method {method} but "
                            "has no `body_brief` and no `raw_body`."
                        ),
                        "fix_hint": (
                            "At plan time, add `parameters.body_brief` (one-sentence "
                            "description of the payload) and `parameters.body_vars` "
                            "(list of Liquid expressions the payload should include). "
                            "Plan-time briefs are cheap — the main agent will expand "
                            "the brief into a full `raw_body` (using "
                            "`lookup_zuora_api_spec` for Zuora APIs) before calling "
                            "`build_workflow_definition`. Only set `raw_body` "
                            "directly when the user supplied the exact JSON."
                        ),
                    }
                )
            if raw_body and len(raw_body) > _PLAN_TIME_CONTENT_WARN_CHARS:
                result["warnings"].append(
                    {
                        "path": f"tasks[{idx}].parameters.raw_body",
                        "code": "CALLOUT_BODY_TOO_LARGE",
                        "message": (
                            f"{action_type} task '{name}' carries a "
                            f"{len(raw_body)}-char `raw_body` at plan time. Callout "
                            "body authoring is a TWO-PHASE process — the plan "
                            "should carry only `body_brief` + `body_vars`, and "
                            "`raw_body` is expanded AFTER `validate_workflow_plan"
                            "(stage='plan', ...)` returns OK and BEFORE "
                            "`build_workflow_definition`."
                        ),
                        "fix_hint": (
                            "Phase 3 (plan validation): set "
                            "`parameters.body_brief` (one-sentence payload "
                            "description) and `parameters.body_vars` (ordered "
                            "Liquid expressions the payload must include). Drop "
                            "`raw_body`. "
                            "Between Phase 3 and Phase 4 (build): expand each "
                            "brief into a real `raw_body` (Liquid-embedded JSON), "
                            "set it on the task's parameters, and drop "
                            "`body_brief` / `body_vars`. The only exception is "
                            "when the user supplied the exact payload — then "
                            "`raw_body` can stay at plan time."
                        ),
                    }
                )
