"""Workflow assembly from plan data.

Replicated from workflow_agent/planning/assembler.py and
workflow_agent/orchestration/nodes/assembly.py.

This module assembles complete workflow JSON from a validated plan dict
using the TaskTemplateEngine for task generation, ModelEnforcementEngine
for parameter whitelisting, and manifest-driven default pruning.

Pipeline::

    assemble_workflow(plan_data, template_engine)
        ├── generate_workflow_config(plan_data)
        ├── generate_tasks(plan_data, template_engine, enforcer)
        │       └── per task: template_engine.generate_task()
        │                     → model_enforcement.enforce()
        │                     → _prune_default_and_empty_parameters()
        ├── generate_linkages(plan_data)
        └── validate_workflow_export_strict(assembled)
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from typing import Any, Optional

from workflow_engine.workflow_reference.data_flow import DataFlowTracker
from workflow_engine.workflow_reference.event_parameters import (
    generate_event_parameters,
    seed_event_data_paths,
)
from workflow_engine.workflow_reference.export_validate import (
    ModelEnforcementEngine,
    validate_workflow_export_strict,
)
from workflow_engine.workflow_reference.liquid_validation import (
    mask_data_liquid_property_reads,
    validate_liquid_references,
    validate_liquid_syntax,
    validate_logic_liquid_data_liquid_reads,
)
from workflow_engine.workflow_reference.models import TASK_LINKAGE_TYPES, TASK_TYPE_CONFIG_MAP
from workflow_engine.workflow_reference.models.generated import (
    WorkflowConfiguration,
    WorkflowConfigurationParameters,
)
from workflow_engine.workflow_reference.plan_validator import iterate_body_map
from workflow_engine.workflow_reference.task_templates import (
    TaskTemplateEngine,
    _resolve_required_for_params,
)
from workflow_engine.workflow_reference.workflow_layout import compute_layout_from_steps

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers: notifications (match Rails DB default of {})
# ---------------------------------------------------------------------------


def _build_notifications(notifications: dict) -> dict:
    """Build the workflow notifications block.

    Rails DB default is {} (empty). Only include keys the plan explicitly sets.
    When notification flags (failure/success/pending) are enabled, Rails validates
    that emails is non-empty — so we include emails only when a flag is on.
    """
    if not notifications:
        return {}
    result: dict[str, Any] = {}
    has_active_flag = False
    for flag in ("failure", "success", "pending", "skipped_scheduled_run"):
        plan_key = f"on_{flag}" if flag in ("failure", "success") else flag
        val = notifications.get(plan_key) or notifications.get(flag)
        if val is not None:
            result[flag] = bool(val)
            if bool(val):
                has_active_flag = True
    if has_active_flag:
        result["emails"] = notifications.get("emails", [])
    if notifications.get("error_ignore"):
        result["error_ignore"] = notifications["error_ignore"]
    return result


# ---------------------------------------------------------------------------
# Helpers: field normalization (from old agent assembly.py)
# ---------------------------------------------------------------------------


def _normalize_fields(fields: Any, object_name: str | None = None) -> dict:
    """Convert fields from list, dict, or string to SOAP-style {Object: {Field: 'true'}}."""
    if isinstance(fields, str) and fields.strip():
        if fields.strip().startswith("{") or fields.strip().startswith("["):
            try:
                fields = json.loads(fields)
            except json.JSONDecodeError:
                return {}
        else:
            fields = _parse_comma_separated_object_fields(fields)
    if isinstance(fields, list) and object_name:
        fields = {object_name: fields}
    if not isinstance(fields, dict):
        return {}
    result = {}
    for obj_name, val in fields.items():
        if isinstance(val, list):
            result[obj_name] = {f: "true" for f in val if isinstance(f, str)}
        elif isinstance(val, dict):
            soap: dict[str, str] = {}
            for fname, fval in val.items():
                if fval == "true" or fval is True:
                    soap[fname] = "true"
                elif isinstance(fval, dict) and len(fval) == 0:
                    soap[fname] = "true"
                else:
                    soap[fname] = str(fval) if fval is not None else "true"
            result[obj_name] = soap
        else:
            result[obj_name] = val
    return result


def _parse_comma_separated_object_fields(csv_str: str) -> dict:
    out: dict[str, list[str]] = {}
    for part in (p.strip() for p in csv_str.split(",") if p.strip()):
        if "." in part:
            obj, _, field = part.partition(".")
            obj, field = obj.strip(), field.strip()
            if obj and field:
                out.setdefault(obj, []).append(field)
    return out


# ---------------------------------------------------------------------------
# Helpers: default pruning (from old agent assembly.py)
# ---------------------------------------------------------------------------

KEEP_PARAMS_EVEN_IF_DEFAULT: frozenset[tuple[str, str]] = frozenset(
    {
        ("Export", "zip"),
        ("Data::Link", "zip"),
    }
)


def _default_value_for_api(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return value


def _get_model_default(config_class: type, field_name: str) -> Any:
    fields = getattr(config_class, "model_fields", {})
    if field_name not in fields:
        return None
    field = fields[field_name]
    default = getattr(field, "default", None)
    if default is not None:
        return _default_value_for_api(default)
    factory = getattr(field, "default_factory", None)
    if factory is not None:
        return _default_value_for_api(factory())
    return None


def _is_empty_or_default(value: Any, default_api: Any) -> bool:
    if value is None or value == "" or value == "''":
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    if default_api is not None and value == default_api:
        return True
    return False


def _recursive_prune_empty(obj: Any) -> None:
    if not isinstance(obj, dict):
        return
    to_drop = []
    for key, value in list(obj.items()):
        if value is None or value == "" or value == "''":
            to_drop.append(key)
            continue
        if isinstance(value, dict):
            _recursive_prune_empty(value)
            if len(value) == 0:
                to_drop.append(key)
        elif isinstance(value, list) and len(value) == 0:
            to_drop.append(key)
    for key in to_drop:
        del obj[key]


_COMMON_PASS_THROUGH_DEFAULTS: dict[str, tuple[Any, ...]] = {
    "strict_variables": (True, "true"),
    "disable_validation": (False, "false"),
    "delete_payload_paths": ([],),
}


def _prune_default_and_empty_parameters(task_json: dict) -> None:
    """Drop non-required parameters that are empty or equal to their default.

    Schema-required fields (unconditional + conditional ``if/then``) are
    never pruned — they were hydrated on purpose by
    :meth:`tools.workflow_reference.task_templates.TaskTemplateEngine._hydrate_required_fields`
    and must survive to the final JSON. Everything else follows the old-branch
    behavior:

    * ``strict_variables = True`` / ``"true"`` — dropped (Rails default)
    * ``disable_validation = False`` / ``"false"`` — dropped
    * ``delete_payload_paths = []`` — dropped
    * ``None`` / ``""`` / empty list / empty dict — dropped
    * value equal to the Pydantic field default (after wire conversion) — dropped
    * ``KEEP_PARAMS_EVEN_IF_DEFAULT`` entries are kept regardless

    Empty nested dicts/lists are pruned recursively to keep the JSON compact.
    """
    action_type = task_json.get("action_type", "")
    params = task_json.get("parameters")
    if not isinstance(params, dict):
        return

    top_required, nested_required = _resolve_required_for_params(action_type, params)
    config_class = TASK_TYPE_CONFIG_MAP.get(action_type)

    to_drop: list[str] = []
    for key, value in list(params.items()):
        if key in top_required:
            continue
        if (action_type, key) in KEEP_PARAMS_EVEN_IF_DEFAULT:
            continue
        if key in _COMMON_PASS_THROUGH_DEFAULTS:
            if value in _COMMON_PASS_THROUGH_DEFAULTS[key]:
                to_drop.append(key)
                continue
        if value is None or value == "" or value == "''":
            to_drop.append(key)
            continue
        if isinstance(value, (list, dict)) and len(value) == 0:
            to_drop.append(key)
            continue
        if config_class is not None:
            default_api = _get_model_default(config_class, key)
            if default_api is not None and value == default_api:
                to_drop.append(key)

    for key in to_drop:
        del params[key]

    _recursive_prune_empty_except(params, top_required, nested_required)


def _recursive_prune_empty_except(
    obj: Any,
    protected: set[str],
    nested_protected: Optional[dict[str, set[str]]] = None,
) -> None:
    """Recursive variant of :func:`_recursive_prune_empty` that leaves any
    top-level key in ``protected`` alone and, for keys in
    ``nested_protected``, preserves the listed sub-keys inside the nested
    dict even if their value is empty (so conditionally-required fields
    survive)."""
    if not isinstance(obj, dict):
        return
    nested_protected = nested_protected or {}
    to_drop: list[str] = []
    for key, value in list(obj.items()):
        if key in protected:
            if isinstance(value, dict):
                _recursive_prune_empty(value)
            continue
        if key in nested_protected and isinstance(value, dict):
            sub_protect = nested_protected[key]
            sub_to_drop: list[str] = []
            for sub_key, sub_value in list(value.items()):
                if sub_key in sub_protect:
                    continue
                if sub_value is None or sub_value == "" or sub_value == "''":
                    sub_to_drop.append(sub_key)
                    continue
                if isinstance(sub_value, dict):
                    _recursive_prune_empty(sub_value)
                    if len(sub_value) == 0:
                        sub_to_drop.append(sub_key)
                elif isinstance(sub_value, list) and len(sub_value) == 0:
                    sub_to_drop.append(sub_key)
            for sub_key in sub_to_drop:
                del value[sub_key]
            continue
        if value is None or value == "" or value == "''":
            to_drop.append(key)
            continue
        if isinstance(value, dict):
            _recursive_prune_empty(value)
            if len(value) == 0:
                to_drop.append(key)
        elif isinstance(value, list) and len(value) == 0:
            to_drop.append(key)
    for key in to_drop:
        del obj[key]


# ---------------------------------------------------------------------------
# Helpers: iterate object resolution (from old agent assembly.py)
# ---------------------------------------------------------------------------


def _resolve_iterate_object(predecessor_task: dict) -> str:
    action_type = predecessor_task.get("action_type", "")
    task_id = predecessor_task.get("id", "")
    params = predecessor_task.get("parameters", {}) or {}
    obj = predecessor_task.get("object", "") or ""

    if action_type == "Query":
        placement = params.get("placement") or obj
        if not placement:
            fields = params.get("fields", {})
            if isinstance(fields, dict) and fields:
                placement = list(fields.keys())[0]
        return placement or "CUSTOM LIQUID"
    elif action_type == "Export":
        zip_param = str(params.get("zip", "true")).lower()
        if zip_param in ("true", "1"):
            return f"{obj}__{task_id}.csv.zip"
        return f"{obj}__{task_id}.csv"
    elif action_type == "Data::Link":
        fmt = params.get("file_format", "json.zip")
        return f"LinkRun__{task_id}.{fmt}"
    elif action_type == "Data::Aqua":
        zip_param = str(params.get("zip", "true")).lower()
        if zip_param in ("true", "1"):
            return f"{obj}__{task_id}.csv.zip"
        return f"{obj}__{task_id}.csv"
    elif action_type == "Data::BillingPreviewRun":
        return f"BillingPreviewRun__{task_id}.csv"
    elif action_type == "Reporting::RunReport":
        return f"report__{task_id}.csv"
    elif action_type == "File::ZuoraImport":
        return f"zuora_import__{task_id}.csv"
    elif action_type == "Logic::CSVTranslator":
        return f"csv_translator__{task_id}.csv"
    return "CUSTOM LIQUID"


_FILE_PRODUCING_TASK_TYPES = frozenset(
    {
        "Export",
        "Data::Link",
        "Data::Aqua",
        "Data::BillingPreviewRun",
        "Reporting::RunReport",
        "File::ZuoraImport",
        "Logic::CSVTranslator",
    }
)


def _resolve_all_iterate_objects(tasks: list[dict], linkages_plan: list[dict]) -> None:
    """Resolve Iterate task `object` from predecessor file output.

    Export/Data::Link/Data::Aqua produce files — the Iterate `object` must
    reference the file (e.g. ``Invoice__<id>.csv.zip``), not the Zuora object.
    Always override LLM-set values when the predecessor produces a file.
    """
    task_map = {t["id"]: t for t in tasks}
    pred_map: dict[int, list[dict]] = defaultdict(list)
    for lnk in linkages_plan:
        from_val = lnk.get("from")
        to_val = lnk.get("to")
        ltype = lnk.get("type", "")
        if isinstance(from_val, int) and to_val is not None and to_val in task_map:
            if ltype in ("Success", "For Each"):
                pred_map[to_val].append(task_map[from_val])
    for task in tasks:
        if task["action_type"] != "Iterate":
            continue
        params = task.setdefault("parameters", {})
        preds = pred_map.get(task["id"], [])
        if len(preds) == 1:
            pred = preds[0]
            resolved = _resolve_iterate_object(pred)
            if pred.get("action_type") in _FILE_PRODUCING_TASK_TYPES:
                task["object"] = resolved
            elif not task.get("object") and not params.get("object"):
                task["object"] = resolved
        elif not task.get("object") and params.get("object"):
            task["object"] = params.pop("object")


# ---------------------------------------------------------------------------
# Helpers: normalize iterate parameters (file vs data iteration)
# ---------------------------------------------------------------------------

_FILE_OBJECT_PATTERN = re.compile(r".*__\d+\.(csv|json)(\.zip)?$", re.IGNORECASE)

_ITERATE_FILE_ONLY_PARAMS = frozenset(
    {
        "file_type",
        "skip_headers",
        "skip_trailer",
        "csv_header_filter",
        "generate_auto_headers",
    }
)


def _normalize_iterate_parameters(tasks: list[dict]) -> None:
    """Strip file-only parameters from data/Liquid Iterate tasks.

    File iteration (object matches ``*__<id>.csv[.zip]``) keeps all params.
    Data iteration (object = array name) and Liquid iteration (object =
    ``CUSTOM LIQUID``) drop file-specific params like ``file_type``,
    ``skip_headers``, etc.
    """
    for task in tasks:
        if task.get("action_type") != "Iterate":
            continue
        obj = task.get("object") or ""
        params = task.get("parameters") or {}
        if not _FILE_OBJECT_PATTERN.match(obj):
            for key in _ITERATE_FILE_ONLY_PARAMS:
                params.pop(key, None)


# ---------------------------------------------------------------------------
# Helpers: callout file references from upstream file-producing tasks
# ---------------------------------------------------------------------------


def _resolve_callout_file_references(tasks: list[dict]) -> None:
    """Populate Callout/AsynchronousCallout ``files`` with references to upstream file outputs.

    Rails stores file references as ``[{"key": "<filename>", "name": "", "upload": "false",
    "filename": ""}]``.  When an Export/Data::Link/etc. task exists in the workflow, any
    downstream Callout task should declare that file in its ``files`` parameter so the
    Callout is aware of available payload files.
    """
    file_refs: list[dict[str, str]] = []
    for task in tasks:
        action_type = task.get("action_type", "")
        if action_type not in _FILE_PRODUCING_TASK_TYPES:
            continue
        tid = task.get("id", "")
        obj = task.get("object", "") or ""
        params = task.get("parameters", {}) or {}
        if action_type == "Export":
            zip_param = str(params.get("zip", "true")).lower()
            ext = ".csv.zip" if zip_param in ("true", "1") else ".csv"
            file_refs.append(
                {
                    "key": f"{obj}__{tid}{ext}",
                    "name": "",
                    "upload": "false",
                    "filename": "",
                }
            )
        elif action_type == "Data::Link":
            fmt = params.get("file_format", "json.zip")
            file_refs.append(
                {
                    "key": f"LinkRun__{tid}.{fmt}",
                    "name": "",
                    "upload": "false",
                    "filename": "",
                }
            )
        elif action_type == "Data::Aqua":
            zip_param = str(params.get("zip", "true")).lower()
            ext = ".csv.zip" if zip_param in ("true", "1") else ".csv"
            file_refs.append(
                {
                    "key": f"{obj}__{tid}{ext}",
                    "name": "",
                    "upload": "false",
                    "filename": "",
                }
            )
    if not file_refs:
        return
    for task in tasks:
        if task.get("action_type") in ("Callout", "AsynchronousCallout"):
            params = task.setdefault("parameters", {})
            existing = params.get("files")
            if not existing or (isinstance(existing, list) and len(existing) == 0):
                params["files"] = list(file_refs)


# ---------------------------------------------------------------------------
# Helpers: fix file-map keys on Upload::SFTP, Upload::FTP, Logic::CSVTranslator
# ---------------------------------------------------------------------------

_FILE_KEY_PATTERN = re.compile(r"^(.+?)__\d+(\..+)$")

_FILE_MAP_CONSUMER_TYPES = frozenset(
    {
        "Upload::SFTP",
        "Upload::FTP",
        "Logic::CSVTranslator",
    }
)


def _build_producer_file_lookup(tasks: list[dict]) -> dict[tuple[str, str], str]:
    """Build ``{(prefix, ext): correct_filename}`` from file-producing tasks."""
    lookup: dict[tuple[str, str], str] = {}
    for task in tasks:
        action_type = task.get("action_type", "")
        if action_type not in _FILE_PRODUCING_TASK_TYPES:
            continue
        tid = task.get("id", "")
        obj = task.get("object", "") or ""
        params = task.get("parameters", {}) or {}
        if action_type == "Export":
            zip_param = str(params.get("zip", "true")).lower()
            ext = ".csv.zip" if zip_param in ("true", "1") else ".csv"
            lookup[(obj, ext)] = f"{obj}__{tid}{ext}"
        elif action_type == "Data::Link":
            fmt = params.get("file_format", "json.zip")
            ext = f".{fmt}"
            lookup[("LinkRun", ext)] = f"LinkRun__{tid}{ext}"
        elif action_type == "Data::Aqua":
            zip_param = str(params.get("zip", "true")).lower()
            ext = ".csv.zip" if zip_param in ("true", "1") else ".csv"
            lookup[(obj, ext)] = f"{obj}__{tid}{ext}"
        elif action_type == "Data::BillingPreviewRun":
            lookup[("BillingPreviewRun", ".csv")] = f"BillingPreviewRun__{tid}.csv"
        elif action_type == "Reporting::RunReport":
            lookup[("report", ".csv")] = f"report__{tid}.csv"
        elif action_type == "File::ZuoraImport":
            lookup[("zuora_import", ".csv")] = f"zuora_import__{tid}.csv"
        elif action_type == "Logic::CSVTranslator":
            lookup[("csv_translator", ".csv")] = f"csv_translator__{tid}.csv"
    return lookup


def _resolve_file_map_references(tasks: list[dict]) -> None:
    """Fix file-map keys on Upload and CSVTranslator tasks to use the producer task's ID."""
    lookup = _build_producer_file_lookup(tasks)
    if not lookup:
        return
    for task in tasks:
        if task.get("action_type") not in _FILE_MAP_CONSUMER_TYPES:
            continue
        params = task.get("parameters") or {}
        files = params.get("files")
        if not isinstance(files, dict) or not files:
            continue
        corrected: dict[str, Any] = {}
        for key, value in files.items():
            m = _FILE_KEY_PATTERN.match(key)
            if m:
                prefix, ext = m.group(1), m.group(2)
                correct_key = lookup.get((prefix, ext)) or key
            else:
                correct_key = key
            corrected[correct_key] = value
        params["files"] = corrected


# ---------------------------------------------------------------------------
# Helpers: chain task_id assignment
# ---------------------------------------------------------------------------


def _assign_chain_task_ids(tasks: list[dict], linkages_plan: list[dict]) -> None:
    starts = [
        lnk.get("to")
        for lnk in linkages_plan
        if str(lnk.get("from")) == "workflow_start" and lnk.get("to") is not None
    ]
    if not starts:
        return
    first = starts[0]
    forward: dict[int, tuple[int, str]] = {}
    for lnk in linkages_plan:
        f = lnk.get("from")
        t = lnk.get("to")
        typ = lnk.get("type", "")
        if not isinstance(f, int) or t is None or typ == "Failure":
            continue
        if f not in forward:
            forward[f] = (t, typ)
        elif forward[f][1] != "Success" and typ == "Success":
            forward[f] = (t, typ)
    chain: list[int] = []
    cur: Optional[int] = first
    seen: set[int] = set()
    while cur is not None and cur not in seen:
        seen.add(cur)
        chain.append(cur)
        nxt = forward.get(cur)
        cur = nxt[0] if nxt else None
    task_by_id = {t["id"]: t for t in tasks}
    for i, tid in enumerate(chain):
        task = task_by_id.get(tid)
        if task:
            task["task_id"] = tid if i == 0 else chain[i - 1]


# ===========================================================================
# Core assembly functions (replicated from old agent)
# ===========================================================================


def generate_workflow_config(plan_data: dict) -> dict:
    """Generate the workflow block (Workflow::Setup) from plan data.

    Equivalent to AssemblyNode._generate_workflow_config + planning/assembler.py
    generate_workflow_config.
    """
    trigger = plan_data.get("trigger", {})
    trigger_type = trigger.get("type", "ondemand")
    notifications = plan_data.get("notifications", {})

    ev_names = trigger.get("event_names") or []
    explicit_ev_params = trigger.get("event_parameters")
    if isinstance(explicit_ev_params, list) and explicit_ev_params:
        event_parameters = explicit_ev_params
    elif trigger_type == "event" and ev_names:
        merged_ep: list[dict] = []
        for ename in ev_names:
            merged_ep.extend(generate_event_parameters(ename))
        event_parameters = merged_ep
    else:
        event_parameters = []

    call_type = plan_data.get("call_type", WorkflowConfiguration.model_fields["call_type"].default)
    ondemand_trigger = trigger_type == "ondemand" or (
        trigger_type == "event" and call_type == "BATCH"
    )

    # Build parameters — only include sub-fields that differ from their model
    # defaults, matching actual Zuora export behavior (event_triggers /
    # event_parameters / fields are the only keys present in a typical export).
    _sentinel = object()
    params: dict[str, Any] = {}
    input_fields = plan_data.get("input_fields", [])
    if input_fields:
        params["fields"] = [
            {
                "field_name": f.get("field_name", ""),
                "object_name": f.get("object_name", ""),
                "datatype": f.get("datatype", "String"),
                "required": f.get("required", False),
                "default": f.get("default", ""),
                "callout_id": f.get("callout_id", ""),
            }
            for f in input_fields
        ]
    if ev_names:
        params["event_triggers"] = ev_names
    if event_parameters:
        params["event_parameters"] = event_parameters
    _param_model_fields = WorkflowConfigurationParameters.model_fields
    for key, field_info in _param_model_fields.items():
        if key in ("fields", "event_triggers", "event_parameters"):
            continue  # already handled above
        val = plan_data.get(key, _sentinel)
        if val is _sentinel:
            continue
        model_default = field_info.default
        if val != model_default:
            params[key] = val

    # Fields whose values are computed from trigger/plan context rather than
    # being simple plan_data passthroughs — applied after the generic loop.
    _computed: dict[str, Any] = {
        "name": plan_data.get("name", "Generated Workflow"),
        "call_type": call_type,
        "ondemand_trigger": ondemand_trigger,
        "callout_trigger": trigger_type == "callout",
        "scheduled_trigger": trigger_type == "scheduled",
        "event_trigger": trigger_type == "event",
        "ui_trigger": trigger_type == "ui" or call_type == "UIACTION",
        "interval": trigger.get("scheduled_interval") or None,
        "timezone": trigger.get("scheduled_timezone") or None,
        "data": {},
        "notifications": _build_notifications(notifications),
        "parameters": params,
    }

    # Build config generically from the model: for every field that has a
    # default, use plan_data if present, otherwise the model default.
    # Fields without a default (only `name`) and fields needing computed
    # logic are skipped here and filled in by _computed above.
    from pydantic_core import PydanticUndefinedType

    config: dict[str, Any] = {}
    for field_name, field_info in WorkflowConfiguration.model_fields.items():
        if field_name == "id":
            continue  # auto-generated by Zuora, never included in imports
        if field_name in _computed or isinstance(field_info.default, PydanticUndefinedType):
            continue
        config[field_name] = plan_data.get(field_name, field_info.default)
    config.update(_computed)
    return config


def generate_tasks(
    plan_data: dict,
    template_engine: TaskTemplateEngine,
    enforcer: ModelEnforcementEngine,
) -> tuple[list[dict], list[str]]:
    """Generate task JSON using the template engine + enforcement + pruning.

    Equivalent to AssemblyNode._generate_tasks (logical plan path):
    for each task → template_engine.generate_task() → enforcer.enforce()
    → _prune_default_and_empty_parameters().
    """
    tasks_plan: list[dict] = plan_data.get("tasks", [])
    linkages_plan: list[dict] = plan_data.get("linkages", [])
    errors: list[str] = []

    # Pre-processing: resolve iterate objects, chain task_ids, file references
    _resolve_all_iterate_objects(tasks_plan, linkages_plan)
    _assign_chain_task_ids(tasks_plan, linkages_plan)
    _resolve_callout_file_references(tasks_plan)
    _resolve_file_map_references(tasks_plan)

    # Ensure Logic::Merge tasks have empty parameters
    for task in tasks_plan:
        if task["action_type"] == "Logic::Merge":
            task.setdefault("parameters", {})
            for key in ("merge_paths", "merge_start", "merge_task_ids"):
                task["parameters"].pop(key, None)

    # Compute CSS positions
    steps = [{"step_id": str(t["id"]), "task_type": t["action_type"]} for t in tasks_plan]
    edges = [
        {
            "from_step": str(lnk.get("from")),
            "to_step": str(lnk.get("to")),
            "edge_type": lnk.get("type", ""),
        }
        for lnk in linkages_plan
        if str(lnk.get("from")) != "workflow_start" and lnk.get("to") is not None
    ]
    css_positions = compute_layout_from_steps(steps, edges)

    priority = plan_data.get("priority", "Medium")
    assembled_tasks: list[dict] = []

    for task in tasks_plan:
        tid = task["id"]
        css = css_positions.get(tid, {"left": "300px", "top": "30px"})

        try:
            task_json = template_engine.generate_task(
                task_id=tid,
                name=task["name"],
                action_type=task["action_type"],
                config=task,
                css=css,
                priority=priority,
            )

            # ModelEnforcementEngine: strip unknown params (manifest as source of truth)
            enforcer.enforce(task_json)

            # Prune defaults and empties (Pydantic model aware)
            _prune_default_and_empty_parameters(task_json)

            # Strip file-only params from data/Liquid Iterate tasks
            _normalize_iterate_parameters([task_json])

            assembled_tasks.append(task_json)
        except Exception as e:
            errors.append(f"Error generating task {tid} ({task.get('name', '')}): {e}")

    return assembled_tasks, errors


# ---------------------------------------------------------------------------
# Linkage validation (source of truth: models.TASK_LINKAGE_TYPES)
# ---------------------------------------------------------------------------
# ``VALID_LINKAGES`` is kept as an alias so existing external imports keep
# working, but the single source of truth is the generated models module.
VALID_LINKAGES: dict[str, list[str] | None] = TASK_LINKAGE_TYPES  # type: ignore[assignment]


def get_valid_linkage_types(task_type: str, case_count: int = 0) -> list[str]:
    """Return valid outgoing linkage types for a task type."""
    if task_type == "Logic::Case":
        types = [f"Case_{i + 1}" for i in range(max(case_count, 2))]
        types.extend(["Case_Else", "Failure"])
        return types
    return VALID_LINKAGES.get(task_type, ["Success", "Failure"])  # type: ignore[return-value]


def validate_linkage(
    source_type: str,
    target_type: str,
    linkage_type: str,
    case_count: int = 0,
    is_back_edge_from_body: bool = False,
) -> list[str]:
    """Validate a single linkage and return list of error strings (empty = valid).

    ``is_back_edge_from_body`` must be True only when the source task is
    located inside the target Iterate's loop body (i.e. reachable from the
    Iterate's ``For Each`` branch).  Legitimate entry edges into an Iterate
    (e.g. ``Export(Success) -> Iterate``) come from outside the body and must
    NOT be flagged — iteration continues after a task in the body completes
    without any explicit back-edge.
    """
    errors: list[str] = []
    valid = get_valid_linkage_types(source_type, case_count)
    if linkage_type not in valid:
        errors.append(
            f"Invalid linkage type '{linkage_type}' from {source_type}. " f"Valid: {valid}"
        )
    if (
        target_type == "Iterate"
        and linkage_type in ("Success", "Failure")
        and is_back_edge_from_body
    ):
        errors.append(
            f"Linking back to Iterate with '{linkage_type}' from inside its "
            "loop body creates an infinite loop. Let the branch terminate; "
            "iteration continues automatically for the next item."
        )
    return errors


def generate_linkages(plan_data: dict) -> tuple[list[dict], list[str]]:
    """Generate assembled linkages (plan format → API format) with validation.

    Returns (assembled_linkages, validation_warnings).
    """
    linkages_plan: list[dict] = plan_data.get("linkages", [])
    tasks_plan: list[dict] = plan_data.get("tasks", [])
    trigger = plan_data.get("trigger", {})
    event_names = trigger.get("event_names") or []
    workflow_id_placeholder = 1
    assembled: list[dict] = []
    warnings: list[str] = []

    task_type_map: dict[int, str] = {t["id"]: t.get("action_type", "") for t in tasks_plan}
    task_by_id: dict[int, dict] = {t["id"]: t for t in tasks_plan if isinstance(t.get("id"), int)}
    iterate_bodies = iterate_body_map(linkages_plan, task_by_id)

    for lnk in linkages_plan:
        from_val = lnk.get("from")
        to_val = lnk.get("to")
        ltype = lnk.get("type", "")

        if str(from_val) == "workflow_start":
            if trigger.get("type") == "event" and event_names:
                ltype = event_names[0]
            assembled.append(
                {
                    "source_workflow_id": workflow_id_placeholder,
                    "source_task_id": None,
                    "target_task_id": to_val,
                    "linkage_type": ltype,
                }
            )
        elif to_val is not None:
            src_type = task_type_map.get(from_val, "")  # type: ignore[arg-type]
            tgt_type = task_type_map.get(to_val, "") if isinstance(to_val, int) else ""
            is_back_edge = (
                tgt_type == "Iterate"
                and isinstance(from_val, int)
                and from_val in iterate_bodies.get(to_val, set())
            )
            errs = validate_linkage(
                src_type,
                tgt_type,
                ltype,
                is_back_edge_from_body=is_back_edge,
            )
            if errs:
                warnings.extend(errs)
            assembled.append(
                {
                    "source_workflow_id": None,
                    "source_task_id": from_val,
                    "target_task_id": to_val,
                    "linkage_type": ltype,
                }
            )

    return assembled, warnings


def generate_workflow_definition(plan_data: dict) -> dict:
    """Generate workflow_definition block."""
    return {
        "name": plan_data.get("name", "Generated Workflow"),
        "description": plan_data.get("description", ""),
        "category": "Default",
        "ui_page_roles": [],
    }


# ===========================================================================
# Main entry point
# ===========================================================================


def assemble_workflow(
    plan_data: dict,
    template_engine: TaskTemplateEngine,
) -> tuple[dict, list[str], list[str]]:
    """Assemble complete workflow JSON from a validated plan dict.

    This is the main entry point for converting a normalized, validated plan
    into schema-compliant workflow JSON. Mirrors the old agent's
    ``planning/assembler.py::assemble_workflow`` + ``AssemblyNode.__call__``.

    Args:
        plan_data: Validated plan dict (post-normalization).
        template_engine: ``TaskTemplateEngine`` instance.

    Returns:
        ``(assembled_json, errors, warnings)``
    """
    enforcer = ModelEnforcementEngine()

    workflow_definition = generate_workflow_definition(plan_data)
    workflow_config = generate_workflow_config(plan_data)
    assembled_tasks, task_errors = generate_tasks(
        plan_data,
        template_engine,
        enforcer,
    )
    assembled_linkages, linkage_warnings = generate_linkages(plan_data)

    assembled_json: dict[str, Any] = {
        "workflow_definition": workflow_definition,
        "workflow": workflow_config,
        "tasks": assembled_tasks,
        "linkages": assembled_linkages,
    }

    strict_ok, strict_errs = validate_workflow_export_strict(assembled_json)

    errors: list[str] = task_errors + strict_errs
    warnings: list[str] = list(linkage_warnings)

    # 4. Data flow tracking
    tracker = DataFlowTracker()
    tracker.available |= seed_event_data_paths(plan_data.get("trigger", {}).get("event_names", []))
    tracker.add_input_fields(plan_data.get("input_fields", []))
    available_before_each_task: list[set[str]] = []
    for task in plan_data.get("tasks", []):
        available_before_each_task.append(set(tracker.available))
        flow_errs = tracker.validate_task_config(
            task["action_type"],
            task.get("parameters", {}),
            task["name"],
        )
        warnings.extend(flow_errs)
        tracker.after_task(
            task["action_type"],
            {
                **task.get("parameters", {}),
                "id": task["id"],
                "object": task.get("object", ""),
                "placement": task.get("parameters", {}).get("placement", ""),
            },
            task["name"],
        )

    # 5. Liquid syntax validation across all tasks
    for i, task in enumerate(plan_data.get("tasks", [])):
        before = available_before_each_task[i] if i < len(available_before_each_task) else set()
        _liquid_validate_task(
            task,
            tracker.available,
            warnings,
            logic_liquid_available_before=before,
        )

    return assembled_json, errors, warnings


def _liquid_validate_task(
    task: dict,
    available_data: set[str],
    warnings: list[str],
    *,
    logic_liquid_available_before: set[str],
) -> None:
    """Run Liquid syntax + reference validation on all text fields of a task."""
    params = task.get("parameters", {})
    task_label = f"task '{task.get('name', task.get('id', '?'))}'"

    fields_to_check: list[tuple[str, str]] = []

    action = task.get("action_type", "")
    if action == "Email":
        email = params.get("email", {})
        if isinstance(email, dict):
            fields_to_check.append(("email.template", email.get("template", "")))
            fields_to_check.append(("email.subject", email.get("subject", "")))
    elif action in ("Callout", "AsynchronousCallout"):
        fields_to_check.append(("raw_body", params.get("raw_body", "")))
    elif action == "If":
        fields_to_check.append(("condition", params.get("condition", "")))
    elif action == "Logic::Liquid":
        fields_to_check.append(("code", params.get("code", "")))

    for field_name, value in fields_to_check:
        if not value or not isinstance(value, str):
            continue
        syntax_errs = validate_liquid_syntax(value)
        for err in syntax_errs:
            warnings.append(f"Liquid syntax in {task_label} {field_name}: {err}")
        if action == "Logic::Liquid" and field_name == "code":
            dl_warns = validate_logic_liquid_data_liquid_reads(value, logic_liquid_available_before)
            for w in dl_warns:
                warnings.append(f"Liquid reference in {task_label} {field_name}: {w}")
            ref_warns = validate_liquid_references(
                mask_data_liquid_property_reads(value),
                logic_liquid_available_before,
            )
        else:
            ref_warns = validate_liquid_references(value, available_data)
        for w in ref_warns:
            warnings.append(f"Liquid reference in {task_label} {field_name}: {w}")
