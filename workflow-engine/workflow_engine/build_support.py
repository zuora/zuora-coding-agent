"""
generate_workflow — DEPRECATED shim for workflow generation.

The original monolithic implementation has been decomposed into four
composable Strands tools:

    lookup_workflow_reference   — canonical Zuora reference data
                                  (events, task catalog, FK relationships, planning guidance)
    validate_workflow_plan      — deterministic intent + plan validation
                                  with blockers/assumptions classification
    build_workflow_definition   — assemble importable workflow JSON from a
                                  validated WorkflowPlan
    import_workflow             — push assembled JSON to the tenant

This module keeps the module-level reference data (manifest, schemas, KB
caches, TASK_CATALOG) and the shared pre-assembly helpers
(``_auto_populate_query_fields``, ``_validate_and_filter_task_fields``,
``_validate_json_schema``, ``_validate_pre_import``,
``analyze_plan_for_optimizations``) that ``build_workflow_definition`` imports.

Known actions delegate to the new tools; unknown/legacy actions return a
deprecation notice that tells the LLM which composable tool to call.
"""

from __future__ import annotations

import json
import re
import typing
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import jsonschema
import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Build TASK_CATALOG from Pydantic models at import time
# ---------------------------------------------------------------------------

_SCHEMA_PATH = Path(__file__).parent / "workflow_reference" / "workflow_export_schema.json"

with _SCHEMA_PATH.open() as _f:
    _WORKFLOW_EXPORT_SCHEMA: dict = json.load(_f)


@dataclass
class ParameterSpec:
    """Schema for a single task parameter (Pydantic-derived)."""

    type: str
    required: bool = False
    liquid: bool = False
    default: Any = None
    description: str = ""
    enum: Optional[List[str]] = None


@dataclass
class TaskSpec:
    """Schema for a single Zuora Workflow task type.

    ``linkage_types`` is ``None`` for tasks with dynamic outgoing edges
    (e.g. Logic::Case with Case_1..Case_N + Case_Else). Callers must branch
    on ``None`` before treating it as a container.
    """

    description: str
    category: str
    requires_object: bool
    parameters: Dict[str, ParameterSpec]
    payload_writes: str = ""
    linkage_types: Optional[List[str]] = field(default=None)
    notes: str = ""


def _type_name_from_annotation(annotation: Any) -> str:
    """Collapse a Pydantic field annotation to a short type name (``str``,
    ``bool``, ``int``, ``list``, ``dict``, ``object``).
    """
    if annotation is None:
        return "str"
    stack = [annotation]
    import types as _types  # local; cheap

    while stack:
        current = stack.pop()
        origin = typing.get_origin(current)
        args = typing.get_args(current)
        if origin is typing.Annotated and args:
            stack.append(args[0])
            continue
        if origin in (typing.Union, _types.UnionType):
            stack.extend(a for a in args if a is not type(None))
            continue
        if current is type(None):
            continue
        if origin is list:
            return "list"
        if origin is dict:
            return "dict"
        if origin is not None and isinstance(origin, type):
            return origin.__name__
        if isinstance(current, type):
            if issubclass(current, bool):
                return "bool"
            if issubclass(current, int):
                return "int"
            if issubclass(current, str):
                return "str"
            return "object"
    return "str"


def _build_task_catalog() -> Dict[str, TaskSpec]:
    """Build ``TASK_CATALOG`` from generated Pydantic models.

    Sources:
      * ``TASK_TYPE_TASK_MAP[action].__doc__`` — task description + ``requires_object``
      * ``TASK_TYPE_CONFIG_MAP[action].model_fields`` — parameter metadata
      * ``TASK_LINKAGE_TYPES`` — valid outgoing linkages per task
    """
    from workflow_engine.workflow_reference.models import (
        TASK_LINKAGE_TYPES,
        TASK_TYPE_CONFIG_MAP,
        TASK_TYPE_TASK_MAP,
        TaskTypeEnum,
    )

    catalog: Dict[str, TaskSpec] = {}
    for member in TaskTypeEnum:
        action = member.value
        task_cls = TASK_TYPE_TASK_MAP.get(action)
        config_cls = TASK_TYPE_CONFIG_MAP.get(action)
        if task_cls is None or config_cls is None:
            continue

        try:
            hints = typing.get_type_hints(config_cls, include_extras=True)
        except Exception:
            hints = {}

        params: Dict[str, ParameterSpec] = {}
        for pname, pfield in config_cls.model_fields.items():
            default = getattr(pfield, "default", None)
            if default is None:
                factory = getattr(pfield, "default_factory", None)
                if factory is not None:
                    try:
                        default = factory()
                    except Exception:
                        default = None
            params[pname] = ParameterSpec(
                type=_type_name_from_annotation(hints.get(pname)),
                required=pfield.is_required(),
                default=default,
                description="",
            )

        obj_field = task_cls.model_fields.get("object")
        requires_object = bool(obj_field and obj_field.is_required())

        linkages = TASK_LINKAGE_TYPES.get(action)
        linkage_types = list(linkages) if linkages is not None else None

        catalog[action] = TaskSpec(
            description=(task_cls.__doc__ or "").strip(),
            category="",
            requires_object=requires_object,
            parameters=params,
            linkage_types=linkage_types,
        )
    return catalog


TASK_CATALOG: Dict[str, TaskSpec] = _build_task_catalog()

from workflow_engine.workflow_reference.models import set_valid_task_types  # noqa: E402

set_valid_task_types(set(TASK_CATALOG.keys()))


# ---------------------------------------------------------------------------
# KB field/relationship loading and ZOQL field helpers
# ---------------------------------------------------------------------------

_KB_FIELDS_PATH = (
    Path(__file__).resolve().parent.parent / "knowledge_base" / "zuora_objects_and_fields.md"
)
_KB_RELATIONSHIPS_PATH = (
    Path(__file__).resolve().parent.parent / "knowledge_base" / "zuora_objects_relationships.md"
)

_OBJECT_FIELDS_CACHE: dict[str, list[str]] = {}
_OBJECT_REFERENCES_CACHE: dict[str, set[str]] = {}
_ZOQL_EXCLUDED_FIELDS = {"customFields", "netsuite", "deleted"}


def _load_object_fields() -> dict[str, list[str]]:
    """Parse zuora_objects_and_fields.md into ``{object_name: [field_names]}``."""
    if _OBJECT_FIELDS_CACHE:
        return _OBJECT_FIELDS_CACHE
    fields_path = _KB_FIELDS_PATH
    if not fields_path.exists():
        fields_path = Path(__file__).parent / "workflow_reference" / "zuora_objects_and_fields.md"
    if not fields_path.exists():
        return {}
    text = fields_path.read_text(encoding="utf-8")
    for block in re.split(r"\n(?=## )", text):
        if not block.strip().startswith("## "):
            continue
        lines = block.splitlines()
        obj_name = lines[0].strip().lstrip("## ").strip()
        fields = [ln.strip().lstrip("-").strip() for ln in lines[1:] if ln.strip().startswith("-")]
        _OBJECT_FIELDS_CACHE[obj_name] = fields
    return _OBJECT_FIELDS_CACHE


def _load_object_references() -> dict[str, set[str]]:
    """Parse ``zuora_objects_relationships.md`` into navigation aliases.

    Returns ``{object_name: {nav_alias_or_relationship_name, ...}}``.  These
    aliases are REST navigation properties (the *related-object name*, not
    the FK column) that should be filtered out of ZOQL/Export field lists
    because they are not real columns.

    Two MD bullet shapes are handled:

    * ``AccountId -> Account (to-one)`` — the *target* on the right of the
      arrow is the navigation alias (``Account``); the FK column on the
      left (``AccountId``) is a real queryable field and is intentionally
      *not* added to the exclusion set.
    * ``BillToContact (to-one, type Contact, via Invoice.Account.BillToContact)``
      — the leading token (``BillToContact``) is the navigation alias.
    """
    if _OBJECT_REFERENCES_CACHE:
        return _OBJECT_REFERENCES_CACHE
    if not _KB_RELATIONSHIPS_PATH.exists():
        return {}
    text = _KB_RELATIONSHIPS_PATH.read_text(encoding="utf-8")

    sections = text.split("# Zuora object relationships and foreign keys")
    if len(sections) < 2:
        return {}
    rel_text = sections[1]

    arrow_pat = re.compile(r"^\s*([A-Za-z0-9_]+)\s*->\s*([A-Za-z0-9_]+)")
    plain_pat = re.compile(r"^\s*([A-Za-z0-9_]+)")

    current_obj: Optional[str] = None
    in_references = False
    for line in rel_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            current_obj = stripped[3:].strip()
            _OBJECT_REFERENCES_CACHE.setdefault(current_obj, set())
            in_references = False
            continue
        if "**References" in stripped:
            in_references = True
            continue
        if "**Referenced by" in stripped:
            in_references = False
            continue
        if not (in_references and current_obj and stripped.startswith("- ")):
            continue
        body = stripped[2:].strip()
        if not body:
            continue
        arrow = arrow_pat.match(body)
        if arrow:
            _OBJECT_REFERENCES_CACHE[current_obj].add(arrow.group(2))
            continue
        plain = plain_pat.match(body)
        if plain:
            _OBJECT_REFERENCES_CACHE[current_obj].add(plain.group(1))

    return _OBJECT_REFERENCES_CACHE


def _resolve_object_name(name: str) -> Optional[list[str]]:
    """Look up fields for an object name with case-insensitive fallback."""
    by_object = _load_object_fields()
    if not by_object:
        return None
    fields = by_object.get(name)
    if fields is not None:
        return fields
    if len(name) > 1:
        alt = name[0] + name[1:].lower()
        fields = by_object.get(alt)
    if fields is not None:
        return fields
    lower = name.lower()
    for obj_name, obj_fields in by_object.items():
        if obj_name.lower() == lower:
            return obj_fields
    return None


def _get_zoql_fields(obj_name: str) -> Optional[list[str]]:
    """Return only ZOQL/Export-valid fields for an object.

    Filters out REST-only fields: relationship navigation properties, FKs
    listed in the relationships file, lowercase collection fields, and
    special fields.
    """
    all_fields = _resolve_object_name(obj_name)
    if all_fields is None:
        return None

    references = _load_object_references()
    ref_set: set[str] = set()
    if references:
        ref_set = references.get(obj_name, set())
        if not ref_set:
            lower = obj_name.lower()
            for robj, rfields in references.items():
                if robj.lower() == lower:
                    ref_set = rfields
                    break

    zoql_fields = []
    for f in all_fields:
        if f in _ZOQL_EXCLUDED_FIELDS:
            continue
        if f in ref_set:
            continue
        if f and f[0].islower():
            continue
        zoql_fields.append(f)
    return zoql_fields


# Preferred SOAP fields per object for Query tasks — selected for business
# usefulness. When the LLM only provides "Id", these are injected from the KB.
_QUERY_PREFERRED_FIELDS: dict[str, list[str]] = {
    "InvoiceItem": [
        "Id",
        "ChargeName",
        "ChargeNumber",
        "SKU",
        "UOM",
        "Balance",
        "Quantity",
        "UnitPrice",
        "ChargeDate",
        "ChargeAmount",
        "Description",
    ],
    "Invoice": [
        "Id",
        "InvoiceNumber",
        "InvoiceDate",
        "DueDate",
        "Amount",
        "Balance",
        "Status",
    ],
    "Payment": [
        "Id",
        "PaymentNumber",
        "Amount",
        "EffectiveDate",
        "Status",
        "Type",
    ],
    "Account": [
        "Id",
        "Name",
        "AccountNumber",
        "Balance",
        "Status",
        "Currency",
    ],
    "Subscription": [
        "Id",
        "Name",
        "SubscriptionStartDate",
        "SubscriptionEndDate",
        "Status",
        "Version",
    ],
    "RatePlan": ["Id", "Name", "AmendmentType", "ProductRatePlanId"],
    "RatePlanCharge": [
        "Id",
        "Name",
        "ChargeNumber",
        "ChargeType",
        "ChargeModel",
        "Quantity",
        "MRR",
        "TCV",
    ],
    "Contact": ["Id", "FirstName", "LastName", "WorkEmail", "WorkPhone"],
    "CreditMemo": [
        "Id",
        "MemoNumber",
        "MemoDate",
        "TotalAmount",
        "Balance",
        "Status",
    ],
    "DebitMemo": [
        "Id",
        "MemoNumber",
        "MemoDate",
        "TotalAmount",
        "Balance",
        "Status",
    ],
    "CreditMemoItem": [
        "Id",
        "Amount",
        "ChargeDate",
        "ChargeName",
        "Quantity",
        "UnitPrice",
        "ServiceStartDate",
        "ServiceEndDate",
    ],
    "DebitMemoItem": [
        "Id",
        "Amount",
        "ChargeDate",
        "ChargeName",
        "Quantity",
        "UnitPrice",
        "ServiceStartDate",
        "ServiceEndDate",
    ],
    "Usage": ["Id", "Quantity", "StartDateTime", "EndDateTime", "UOM", "SourceType"],
    "Amendment": [
        "Id",
        "Name",
        "Type",
        "Status",
        "ContractEffectiveDate",
        "EffectiveDate",
    ],
    "Order": ["Id", "OrderNumber", "OrderDate", "Status", "Description"],
    "Product": [
        "Id",
        "Name",
        "SKU",
        "Description",
        "EffectiveStartDate",
        "EffectiveEndDate",
    ],
    "ProductRatePlan": [
        "Id",
        "Name",
        "Description",
        "EffectiveStartDate",
        "EffectiveEndDate",
    ],
    "ProductRatePlanCharge": [
        "Id",
        "Name",
        "ChargeType",
        "ChargeModel",
        "UOM",
    ],
}


def _get_query_fields_for_object(obj_name: str) -> list[str]:
    """Return the best set of SOAP fields for a Query task on the given object."""
    if obj_name in _QUERY_PREFERRED_FIELDS:
        preferred = _QUERY_PREFERRED_FIELDS[obj_name]
        zoql_fields = _get_zoql_fields(obj_name)
        if zoql_fields is not None:
            valid_set = set(zoql_fields)
            return [f for f in preferred if f in valid_set]
        return preferred

    zoql_fields = _get_zoql_fields(obj_name)
    if zoql_fields is None:
        return []

    audit_fields = {
        "CreatedById",
        "CreatedDate",
        "UpdatedById",
        "UpdatedDate",
        "CreatedBy",
        "UpdatedBy",
    }
    useful = [f for f in zoql_fields if f not in audit_fields]
    result = ["Id"] if "Id" in zoql_fields else []
    result.extend(useful[:12])
    if "Id" in result and result[0] != "Id":
        result.remove("Id")
        result.insert(0, "Id")
    return result


def _normalize_zoql_where_clause(where_clause: str, object_name: str) -> str:
    """Normalize a where_clause for Query tasks to ZOQL format (bare field names)."""
    if not object_name:
        return where_clause
    prefix = object_name + "."
    return re.sub(r"\b" + re.escape(prefix) + r"(\w+)", r"\1", where_clause)


def _auto_populate_query_fields(tasks: list[dict]) -> list[str]:
    """Auto-populate Query task fields from KB SOAP fields when only 'Id' is present.

    Also normalizes Query where_clauses to ZOQL (bare field names).
    Returns a list of info strings describing what changed.
    """
    info: list[str] = []
    for task in tasks:
        action_type = task.get("action_type", "")
        if action_type != "Query":
            continue

        params = task.get("parameters") or {}
        obj_name = task.get("object") or ""
        fields = params.get("fields")

        if not obj_name:
            continue

        if isinstance(fields, dict):
            for fobj, fvals in fields.items():
                is_minimal = False
                if isinstance(fvals, dict):
                    is_minimal = set(fvals.keys()) <= {"Id"}
                elif isinstance(fvals, list):
                    is_minimal = set(fvals) <= {"Id"}

                if is_minimal:
                    preferred = _get_query_fields_for_object(fobj)
                    if preferred:
                        params["fields"] = {fobj: {f: "true" for f in preferred}}
                        info.append(
                            f"Task '{task.get('name', '')}': auto-populated "
                            f"{len(preferred)} SOAP fields for '{fobj}' from knowledge base."
                        )
        elif fields is None and obj_name:
            preferred = _get_query_fields_for_object(obj_name)
            if preferred:
                params["fields"] = {obj_name: {f: "true" for f in preferred}}
                info.append(
                    f"Task '{task.get('name', '')}': auto-populated "
                    f"{len(preferred)} SOAP fields for '{obj_name}' from knowledge base."
                )

        where_clause = params.get("where_clause")
        if isinstance(where_clause, str) and where_clause.strip():
            normalized_wc = _normalize_zoql_where_clause(where_clause, obj_name)
            if normalized_wc != where_clause:
                params["where_clause"] = normalized_wc

    return info


_FIELD_FILTER_TASK_TYPES = (
    "Export",
    "Query",
    "GraphQuery",
    "Data::Aqua",
    "Data::Link",
    "Create",
    "Update",
)


def _field_predicate_for(action_type: str):
    """Return a predicate that decides whether a ``FieldInfo`` is valid for
    ``action_type`` based on the live ``/describe`` metadata.

    * ``Export`` -> ``selectable`` AND ``"export" in contexts`` (AQuA export).
    * ``Query`` / ``GraphQuery`` / ``Data::Aqua`` / ``Data::Link`` -> ``selectable``.
    * ``Create`` -> ``createable``.
    * ``Update`` -> ``updateable``.
    """
    if action_type == "Export":
        return lambda f: f.is_exportable()
    if action_type == "Query":
        return lambda f: f.is_queryable()
    if action_type in ("GraphQuery", "Data::Aqua", "Data::Link"):
        return lambda f: f.selectable
    if action_type == "Create":
        return lambda f: f.createable
    if action_type == "Update":
        return lambda f: f.updateable
    return lambda f: f.selectable


_TO_MANY_CARDINALITIES = frozenset({"TO_MANY", "ONE_TO_MANY", "MANY_TO_MANY"})


def _is_to_one_ref(ref: dict) -> bool:
    card = (ref.get("cardinality") or "").upper()
    if card in _TO_MANY_CARDINALITIES:
        return False
    label = (ref.get("raw_label") or "").lower()
    if "one-to-many" in label or "many-to-many" in label or "to-many" in label:
        return False
    return True


def _describe_valid_field_names(describe: Any, predicate) -> Optional[set[str]]:
    """Return the set of valid field names for ``predicate``, or ``None``
    when the describe has no field data (caller should fall back)."""
    if describe is None or not getattr(describe, "fields", None):
        return None
    return {f.name for f in describe.fields if predicate(f)}


async def _validate_and_filter_task_fields(
    tasks: list[dict],
    *,
    tool_context: Any = None,
    relationships_graph: Optional[dict] = None,
) -> tuple[list[str], list[str]]:
    """Validate and triage ``Export`` / ``Query`` / ``GraphQuery`` /
    ``Data::Aqua`` / ``Data::Link`` / ``Create`` / ``Update`` ``fields``
    against live ``/v1/describe`` schemas.

    Three triage outcomes per invalid ``(source_obj, field_name)`` pair:

    1. **Relocate** — when exactly one candidate object key holds
       ``field_name`` (per the task-type predicate). "Candidate" means
       either (a) another object key already present in ``fields``, or
       (b) a 1:1 / N:1 related object reachable from ``source_obj`` via
       ``relationships_graph``. The field moves from
       ``fields[source_obj]`` into ``fields[candidate]`` (the key is
       created when missing).
    2. **Block** — when two or more candidates match, emit a blocking
       error (``FIELD_AMBIGUOUS_OBJECT_KEY``) listing the candidates so
       the main agent can place the field under the correct key. The
       field stays where the agent put it — no relocation, no removal —
       so the build loop can retry after the agent rewrites the plan.
    3. **Remove** — when zero candidates match, fall back to the legacy
       "remove + warn" behavior.

    Returns a ``(warnings, blocking_errors)`` tuple. The caller should
    halt the build when ``blocking_errors`` is non-empty.
    """
    from workflow_engine.workflow_reference.object_metadata import get_object_metadata

    target_tasks = [
        t
        for t in tasks
        if t.get("action_type", "") in _FIELD_FILTER_TASK_TYPES
        and isinstance((t.get("parameters") or {}).get("fields"), dict)
    ]
    if not target_tasks:
        return ([], [])

    # Collect every object we may need a describe for: explicit fields keys
    # PLUS every 1:1 / N:1 related object reachable from each fields key.
    distinct_objects: set[str] = set()
    for task in target_tasks:
        for obj_name in (task.get("parameters") or {}).get("fields", {}):
            distinct_objects.add(obj_name)
    if relationships_graph:
        for base in list(distinct_objects):
            for ref in (relationships_graph.get(base) or {}).get("references") or []:
                if not _is_to_one_ref(ref):
                    continue
                target = ref.get("target_object")
                if isinstance(target, str) and target:
                    distinct_objects.add(target)

    describes: dict[str, Any] = {}
    for obj_name in distinct_objects:
        try:
            result = await get_object_metadata(obj_name, tool_context=tool_context)
            describes[obj_name] = result.describe if result else None
        except Exception:
            describes[obj_name] = None

    warnings: list[str] = []
    blocking_errors: list[str] = []

    for task in target_tasks:
        action_type = task.get("action_type", "")
        params = task.get("parameters") or {}
        fields = params["fields"]
        task_name = task.get("name", "")
        predicate = _field_predicate_for(action_type)

        # Per-key valid-field lookup, honoring the knowledge-base fallback
        # when the resolver cannot describe the object.
        key_valid_sets: dict[str, Optional[set[str]]] = {}
        for obj_name in list(fields.keys()):
            describe = describes.get(obj_name)
            valid_set = _describe_valid_field_names(describe, predicate)
            if valid_set is None:
                fallback_fields = _get_zoql_fields(obj_name)
                if fallback_fields is not None:
                    valid_set = set(fallback_fields)
            key_valid_sets[obj_name] = valid_set

        present_keys: list[str] = list(fields.keys())
        relocations: dict[tuple[str, str], str] = {}
        ambiguous: set[tuple[str, str]] = set()

        for obj_name, obj_fields in fields.items():
            for fname in _field_name_iter(obj_fields):
                valid_set = key_valid_sets.get(obj_name)
                if valid_set is None or fname in valid_set:
                    continue

                candidates = _find_relocation_candidates(
                    source_obj=obj_name,
                    field_name=fname,
                    present_keys=present_keys,
                    describes=describes,
                    predicate=predicate,
                    relationships_graph=relationships_graph,
                )
                if len(candidates) == 1:
                    relocations[(obj_name, fname)] = candidates[0]
                elif len(candidates) > 1:
                    ambiguous.add((obj_name, fname))
                    blocking_errors.append(
                        f"Task '{task_name}': field '{fname}' placed under "
                        f"'{obj_name}' does not belong to that object but matches "
                        f"{len(candidates)} related objects: {candidates}. Move "
                        f"'{fname}' under the correct related object key in "
                        f"`parameters.fields` (code: FIELD_AMBIGUOUS_OBJECT_KEY)."
                    )

        # Rebuild fields with filtering + relocation in a single pass.
        new_fields: dict[str, Any] = {}
        for obj_name, obj_fields in fields.items():
            valid_set = key_valid_sets.get(obj_name)
            if valid_set is None:
                new_fields[obj_name] = obj_fields
                warnings.append(
                    f"Task '{task_name}': object '{obj_name}' not found via "
                    "/describe or knowledge base - cannot validate fields."
                )
                continue

            if isinstance(obj_fields, dict):
                cleaned_dict: dict[str, str] = {}
                for fname, fval in obj_fields.items():
                    if fname in valid_set:
                        cleaned_dict[fname] = fval
                        continue
                    if (obj_name, fname) in ambiguous:
                        # Block path: preserve original placement.
                        cleaned_dict[fname] = fval
                        continue
                    target_key = relocations.get((obj_name, fname))
                    if target_key:
                        target_dict = new_fields.setdefault(target_key, {})
                        if isinstance(target_dict, list):
                            if fname not in target_dict:
                                target_dict.append(fname)
                            new_fields[target_key] = target_dict
                        else:
                            target_dict[fname] = fval
                            new_fields[target_key] = target_dict
                        warnings.append(
                            f"Task '{task_name}': relocated field '{fname}' from "
                            f"'{obj_name}' to '{target_key}' (owner per /describe)."
                        )
                        continue
                    warnings.append(
                        f"Task '{task_name}': removed field "
                        f"'{obj_name}.{fname}' (not valid for {action_type})."
                    )
                if not cleaned_dict:
                    cleaned_dict = {"Id": "true"}
                    warnings.append(
                        f"Task '{task_name}': all fields were invalid for "
                        f"'{obj_name}', defaulting to 'Id'."
                    )
                # Preserve any relocations already added under obj_name.
                existing = new_fields.get(obj_name)
                if isinstance(existing, dict):
                    existing.update(cleaned_dict)
                    new_fields[obj_name] = existing
                else:
                    new_fields[obj_name] = cleaned_dict

            elif isinstance(obj_fields, list):
                cleaned_list: list[str] = []
                removed: list[str] = []
                for fname in obj_fields:
                    if fname in valid_set:
                        cleaned_list.append(fname)
                        continue
                    if (obj_name, fname) in ambiguous:
                        cleaned_list.append(fname)
                        continue
                    target_key = relocations.get((obj_name, fname))
                    if target_key:
                        target = new_fields.setdefault(target_key, [])
                        if isinstance(target, dict):
                            target[fname] = "true"
                        elif fname not in target:
                            target.append(fname)
                        new_fields[target_key] = target
                        warnings.append(
                            f"Task '{task_name}': relocated field '{fname}' from "
                            f"'{obj_name}' to '{target_key}' (owner per /describe)."
                        )
                        continue
                    removed.append(fname)
                if removed:
                    warnings.append(
                        f"Task '{task_name}': removed fields from '{obj_name}' "
                        f"(not valid for {action_type}): {removed}."
                    )
                if not cleaned_list:
                    cleaned_list = ["Id"]
                existing = new_fields.get(obj_name)
                if isinstance(existing, list):
                    for f in cleaned_list:
                        if f not in existing:
                            existing.append(f)
                    new_fields[obj_name] = existing
                else:
                    new_fields[obj_name] = cleaned_list
            else:
                new_fields[obj_name] = obj_fields

        params["fields"] = new_fields

    return warnings, blocking_errors


def _field_name_iter(obj_fields: Any):
    """Yield field names for either the dict-of-flags or list shape."""
    if isinstance(obj_fields, dict):
        yield from (f for f in obj_fields.keys() if isinstance(f, str))
    elif isinstance(obj_fields, list):
        yield from (f for f in obj_fields if isinstance(f, str))


def _find_relocation_candidates(
    *,
    source_obj: str,
    field_name: str,
    present_keys: list[str],
    describes: dict[str, Any],
    predicate,
    relationships_graph: Optional[dict],
) -> list[str]:
    """Return candidate object keys that validly own ``field_name``.

    Priority order: (1) object keys already present in ``fields`` win
    over (2) related objects reachable via the relationships graph.
    Deduplicates while preserving discovery order.
    """
    seen: set[str] = set()
    ordered: list[str] = []

    for key in present_keys:
        if key == source_obj or key in seen:
            continue
        valid_set = _describe_valid_field_names(describes.get(key), predicate)
        if valid_set is None:
            continue
        if field_name in valid_set:
            ordered.append(key)
            seen.add(key)

    if relationships_graph:
        for ref in (relationships_graph.get(source_obj) or {}).get("references") or []:
            if not _is_to_one_ref(ref):
                continue
            target = ref.get("target_object")
            if not isinstance(target, str) or not target:
                continue
            if target in seen or target == source_obj:
                continue
            valid_set = _describe_valid_field_names(describes.get(target), predicate)
            if valid_set is None:
                continue
            if field_name in valid_set:
                ordered.append(target)
                seen.add(target)

    return ordered


# ---------------------------------------------------------------------------
# JSON Schema + pre-import Rails rule validation
# ---------------------------------------------------------------------------


def _validate_json_schema(workflow_json: dict) -> list[str]:
    """Validate assembled workflow JSON against workflow_export_schema.json."""
    errors: list[str] = []
    try:
        jsonschema.validate(instance=workflow_json, schema=_WORKFLOW_EXPORT_SCHEMA)
    except jsonschema.ValidationError as e:
        errors.append(f"JSON Schema error at {list(e.absolute_path)}: {e.message}")
    except jsonschema.SchemaError as e:
        errors.append(f"Schema definition error: {e.message}")
    return errors


def _validate_no_for_each_before_merge(
    tasks: list[dict],
    linkages: list[dict],
) -> list[str]:
    """Validate that no 'For Each' linkage appears on any path leading to Logic::Merge."""
    errors: list[str] = []
    merge_task_ids = {t["id"] for t in tasks if t.get("action_type") == "Logic::Merge"}
    if not merge_task_ids:
        return errors

    pred_map: dict[int, list[tuple]] = defaultdict(list)
    for lnk in linkages:
        src = lnk.get("source_task_id")
        tgt = lnk.get("target_task_id")
        ltype = lnk.get("linkage_type", "")
        if src is not None and tgt is not None:
            pred_map[tgt].append((src, ltype))

    for merge_id in merge_task_ids:
        visited: set[int] = set()
        stack = [merge_id]
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            for src_id, ltype in pred_map.get(node, []):
                if ltype == "For Each":
                    errors.append(
                        f"Logic::Merge task (id={merge_id}) has a 'For Each' linkage on "
                        f"its path from task id={src_id}. For Each linkages cannot precede "
                        f"a merge point. Use a separate workflow or restructure the loop."
                    )
                else:
                    stack.append(src_id)

    return errors


def _validate_pre_import(workflow_json: dict) -> tuple[list[str], list[str]]:
    """Validate assembled workflow JSON against known Rails server-side rules.

    Returns ``(errors, warnings)``. Errors block import; warnings are informational.
    """
    errors: list[str] = []
    warnings: list[str] = []
    wf = workflow_json.get("workflow", {})
    tasks = workflow_json.get("tasks", [])
    linkages = workflow_json.get("linkages", [])

    version = wf.get("version", "")
    if not re.match(r"^\d+(?:\.\d+)?(?:\.\d+)?$", str(version)):
        errors.append(
            f"Invalid version format '{version}'. Must be semantic version: " "'1.0.0', '2.1', etc."
        )

    if wf.get("scheduled_trigger"):
        interval = wf.get("interval", "")
        if not interval:
            errors.append("scheduled_trigger is true but interval is missing.")
        else:
            parts = str(interval).split()
            if len(parts) not in (5, 6):
                errors.append(
                    f"Scheduled interval '{interval}' does not look like a valid cron "
                    "expression (expected 5 or 6 fields, e.g. '0 8 * * *')."
                )
        tz = wf.get("timezone", "")
        if not tz:
            errors.append("scheduled_trigger is true but timezone is missing.")
        else:
            if "/" not in tz and tz not in ("UTC", "EST", "PST", "CST", "MST"):
                warnings.append(
                    f"Timezone '{tz}' may not be a valid Rails timezone name. "
                    "Use IANA format: 'America/Los_Angeles', 'Europe/London', 'UTC'."
                )

    if wf.get("event_trigger"):
        event_triggers = wf.get("parameters", {}).get("event_triggers", [])
        if not event_triggers:
            errors.append("event_trigger is true but parameters.event_triggers is empty.")

    if wf.get("callout_trigger"):
        for fld in wf.get("parameters", {}).get("fields", []):
            if fld.get("required") and not fld.get("callout_id"):
                errors.append(
                    f"Input field '{fld.get('field_name')}' is required but has no "
                    "callout_id. Callout-triggered workflows need callout_id for "
                    "required fields."
                )

    delete_ttl = wf.get("delete_ttl", 30)
    try:
        ttl_val = int(delete_ttl)
        if ttl_val < 0:
            errors.append(f"delete_ttl must be >= 0. Got: {delete_ttl}.")
        elif ttl_val > 45:
            warnings.append(
                f"delete_ttl={delete_ttl} exceeds the non-production default maximum of 45."
            )
    except (TypeError, ValueError):
        pass

    for email_addr in wf.get("notifications", {}).get("emails", []):
        if "@" not in str(email_addr):
            errors.append(f"Notification email '{email_addr}' does not look like a valid address.")

    # --- Task-level ---
    for task in tasks:
        name = task.get("name", "")
        tid = task.get("id")
        action_type = task.get("action_type", "")
        params = task.get("parameters", {})

        if not name or not name.strip():
            errors.append(f"Task id={tid} has a blank name.")

        if str(params.get("disable_validation", "false")).lower() == "true":
            errors.append(
                f"Task '{name}' (id={tid}) has disable_validation=true. "
                "This masks configuration errors and must not be set in generated workflows."
            )

        if action_type == "Callout":
            if not params.get("url"):
                errors.append(
                    f"Callout task '{name}' (id={tid}) is missing required parameter: url."
                )
            retry = params.get("retry_rules", {}) or {}
            try:
                rc = int(retry.get("retry_count", 0))
                if not (0 <= rc <= 10):
                    errors.append(f"Callout task '{name}': retry_count must be 0–10, got {rc}.")
            except (TypeError, ValueError):
                pass
            try:
                rw = int(retry.get("retry_window", 30))
                if not (0 <= rw <= 60):
                    errors.append(
                        f"Callout task '{name}': retry_window must be 0–60 min, got {rw}."
                    )
            except (TypeError, ValueError):
                pass
            pl = (params.get("validation") or {}).get("payload_location", "")
            if pl and not re.match(r"^[a-zA-Z0-9_]+$", pl):
                errors.append(
                    f"Callout task '{name}': payload_location '{pl}' contains invalid "
                    "characters. Must be alphanumeric + underscore only."
                )

        if action_type in ("Query", "Export", "Create", "Update"):
            fields = params.get("fields", {})
            if isinstance(fields, dict):
                total_fields = sum(len(v) for v in fields.values() if isinstance(v, dict))
                if total_fields == 0:
                    errors.append(f"{action_type} task '{name}' (id={tid}) has no fields selected.")
                for obj_name, obj_fields in fields.items():
                    zoql_fields = _get_zoql_fields(obj_name)
                    if zoql_fields is not None and isinstance(obj_fields, dict):
                        valid_set = set(zoql_fields)
                        invalid = [f for f in obj_fields if f not in valid_set]
                        if invalid:
                            warnings.append(
                                f"{action_type} task '{name}' (id={tid}): fields {invalid} "
                                f"are not ZOQL-exportable for '{obj_name}'."
                            )

        if action_type in ("Update", "Delete"):
            if not task.get("object_id"):
                errors.append(f"{action_type} task '{name}' (id={tid}) is missing object_id.")

        if action_type == "Logic::ResponseFormatter":
            for req_param in ("code", "template", "processor"):
                if not params.get(req_param):
                    errors.append(
                        f"Logic::ResponseFormatter task '{name}' (id={tid}) is missing "
                        f"required parameter: {req_param}."
                    )

        if action_type == "Execute::WorkflowTask":
            if not params.get("workflow_id"):
                errors.append(f"Execute::WorkflowTask '{name}' (id={tid}) is missing workflow_id.")

        if action_type == "Email":
            email_params = params.get("email", {}) or {}
            for req_param in ("to", "from", "subject", "template"):
                if not email_params.get(req_param):
                    errors.append(
                        f"Email task '{name}' (id={tid}) is missing required email "
                        f"parameter: {req_param}."
                    )

        if action_type == "Data::Link":
            if not params.get("query"):
                errors.append(
                    f"Data::Link task '{name}' (id={tid}) is missing required parameter: query."
                )

        if action_type == "If":
            if not params.get("if_clause"):
                errors.append(
                    f"If task '{name}' (id={tid}) is missing required parameter: if_clause."
                )

        if action_type == "Logic::Case":
            if not params.get("case_clause"):
                errors.append(f"Logic::Case task '{name}' (id={tid}) is missing case_clause.")
            if not params.get("case_condition"):
                errors.append(
                    f"Logic::Case task '{name}' (id={tid}) has no case_condition entries."
                )

        if action_type == "Delay":
            if not params.get("delay_time"):
                errors.append(
                    f"Delay task '{name}' (id={tid}) is missing required parameter: delay_time."
                )

        if action_type == "Iterate":
            if not task.get("object") and not params.get("object"):
                errors.append(f"Iterate task '{name}' (id={tid}) is missing the object field.")

    # --- Linkage-level ---
    linkage_keys: set[tuple] = set()
    for lnk in linkages:
        key = (
            lnk.get("source_task_id"),
            lnk.get("target_task_id"),
            lnk.get("linkage_type"),
        )
        if key in linkage_keys:
            errors.append(
                f"Duplicate linkage: source={key[0]} → target={key[1]} type={key[2]}. "
                "Linkages must be unique."
            )
        linkage_keys.add(key)

    errors.extend(_validate_no_for_each_before_merge(tasks, linkages))

    task_map = {t["id"]: t for t in tasks}
    for lnk in linkages:
        src_id = lnk.get("source_task_id")
        ltype = lnk.get("linkage_type", "")
        if src_id and src_id in task_map:
            src_type = task_map[src_id].get("action_type", "")
            if src_type in TASK_CATALOG:
                valid = TASK_CATALOG[src_type].linkage_types
                if valid is None:
                    if not (ltype.startswith("Case_") or ltype == "Case_Else"):
                        errors.append(
                            f"Linkage type '{ltype}' is not valid for dynamic "
                            f"task type '{src_type}'. Valid types: Case_1..Case_N, "
                            f"Case_Else."
                        )
                elif not ltype.startswith("Case_") and ltype not in valid:
                    errors.append(
                        f"Linkage type '{ltype}' is not valid for task type '{src_type}'. "
                        f"Valid types: {valid}."
                    )

    return errors, warnings


# ---------------------------------------------------------------------------
# Plan optimization suggestions
# ---------------------------------------------------------------------------


def analyze_plan_for_optimizations(
    tasks: list[dict],
    linkages: list[dict],
) -> list[str]:
    """Analyze a plan for common optimization opportunities.

    Returns a list of human-readable suggestion strings.
    """
    suggestions: list[str] = []
    task_map = {t["id"]: t for t in tasks}

    succ_map: dict[Any, list[tuple]] = defaultdict(list)
    for lnk in linkages:
        src = lnk.get("from")
        tgt = lnk.get("to")
        ltype = lnk.get("type", "")
        if src and tgt and str(src) != "workflow_start":
            succ_map[src].append((tgt, ltype))

    array_returning = {
        "Query",
        "Export",
        "Data::Link",
        "Data::Aqua",
        "Data::Warehouse",
        "Data::BillingPreviewRun",
    }

    for task in tasks:
        tid = task["id"]
        atype = task.get("action_type", "")
        successors = succ_map.get(tid, [])
        success_succs = [task_map[s] for s, lt in successors if lt == "Success" and s in task_map]

        if atype == "Query" and len(success_succs) == 1:
            next_task = success_succs[0]
            if next_task.get("action_type") == "If":
                clause = next_task.get("parameters", {}).get("if_clause", "")
                obj = task.get("object", "")
                if obj and f"Data.{obj}." in clause:
                    suggestions.append(
                        f"Optimization — Query + If consolidation: Task '{task['name']}' "
                        f"(Query on {obj}) followed by '{next_task['name']}' (If checking "
                        f"Data.{obj}.*) can be simplified. Move the condition into the "
                        "Query's where_clause and set zero_query_proceed=true."
                    )

        if atype == "If":
            chain = [task]
            current_succs = success_succs
            while current_succs and current_succs[0].get("action_type") == "If":
                chain.append(current_succs[0])
                current_succs = [
                    task_map[s]
                    for s, lt in succ_map.get(current_succs[0]["id"], [])
                    if lt == "Success" and s in task_map
                ]
            if len(chain) >= 3:
                suggestions.append(
                    f"Optimization — If chain consolidation: Tasks "
                    f"{[t['name'] for t in chain]} are {len(chain)} sequential If tasks. "
                    "Consider replacing with a single Logic::Case task."
                )

        if atype in array_returning:
            pass

    object_queries: dict[str, list[str]] = defaultdict(list)
    for task in tasks:
        if task.get("action_type") == "Query":
            obj = task.get("object", "")
            if obj:
                object_queries[obj].append(task["name"])
    for obj, names in object_queries.items():
        if len(names) > 1:
            suggestions.append(
                f"Optimization — Duplicate queries: Tasks {names} all query the "
                f"'{obj}' object separately. Consider consolidating into a single "
                "Query with a broader WHERE clause."
            )

    return suggestions
