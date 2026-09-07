"""Task template engine: produces correct task JSON from Pydantic models.

The generated ``*Parameters`` models in ``models.generated`` are the source of
truth for allowed parameter names, field types, and defaults. This module
applies the wire-format transformations Zuora/Rails expects *on top* of that
schema:

1. Parameter whitelist — only fields declared on ``<Action>TaskParameters``
   (plus common/Callout pass-throughs) survive.
2. Value conversion — ``bool → "true"/"false"``; dict/list stringified when
   the field is typed ``str`` (e.g. legacy string-in-a-string Rails columns).
3. Nesting — auto-wrap flat amendment/invoice fields under the wrapper key
   Rails expects (``Suspend``/``Resume``/``Cancel``/``InvoiceGenerate``/etc.).
4. Schema-driven required hydration — fill any schema-``required`` field the
   agent omitted (unconditional + conditional ``if/then``) with its Pydantic
   default so the final JSON always carries the declared "structural" keys.
5. Common params — skip ``strict_variables=True``, ``disable_validation=False``,
   empty ``delete_payload_paths``.
"""

from __future__ import annotations

import json
import types
import typing
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from workflow_engine.workflow_reference.models import TASK_TYPE_CONFIG_MAP

# ---------------------------------------------------------------------------
# Wire-format policy tables (task-type specific behavior Rails mandates)
# ---------------------------------------------------------------------------

REST_ONLY_TASK_TYPES = frozenset({"Suspend", "Resume", "Cancel", "InvoiceGenerate"})

# Task types where flat amendment/invoice fields must be nested under a
# wrapper key Rails expects.
FLAT_FIELDS_WRAPPER: dict[str, tuple[str, frozenset[str]]] = {
    "Suspend": (
        "Amendment",
        frozenset(
            {
                "suspendPolicy",
                "suspendPeriodsType",
                "suspendPeriods",
                "suspendSpecificDate",
                "ContractEffectiveDate",
                "contractEffectiveDate",
                "extendsTerm",
            }
        ),
    ),
    "Resume": (
        "Amendment",
        frozenset(
            {
                "resumePolicy",
                "resumePeriodsType",
                "resumePeriods",
                "resumeSpecificDate",
                "ContractEffectiveDate",
                "contractEffectiveDate",
                "extendsTerm",
            }
        ),
    ),
    "Cancel": (
        "Amendment",
        frozenset(
            {
                "cancellationPolicy",
                "cancellationEffectiveDate",
                "ContractEffectiveDate",
                "contractEffectiveDate",
            }
        ),
    ),
    "NewProduct": (
        "Amendment",
        frozenset(
            {
                "ContractEffectiveDate",
                "CustomerAcceptanceDate",
                "Description",
                "Name",
                "RatePlanId",
                "ServiceActivationDate",
            }
        ),
    ),
    "RemoveProduct": (
        "Amendment",
        frozenset(
            {
                "ContractEffectiveDate",
                "CustomerAcceptanceDate",
                "Description",
                "Name",
                "RatePlanId",
                "ServiceActivationDate",
            }
        ),
    ),
    "InvoiceGenerate": (
        "Invoice",
        frozenset(
            {
                "IgnoreBlankInvoices",
                "IncludesOneTime",
                "IncludesRecurring",
                "IncludesUsage",
                "InvoiceDate",
                "TargetDate",
            }
        ),
    ),
    "WriteOff": (
        "write_off",
        frozenset(
            {
                "AdjustmentDate",
                "ChargesOnly",
                "Comment",
                "DeferredRevenueAccount",
                "ReasonCode",
                "RecognizedRevenueAccount",
                "ReferenceId",
                "adjust_taxation_items",
                "single_transaction",
            }
        ),
    ),
}

# (action_type, param_name) pairs that must be kept even when equal to the
# model default.
KEEP_EVEN_IF_DEFAULT: frozenset[tuple[str, str]] = frozenset(
    {
        ("Export", "zip"),
        ("Data::Link", "zip"),
    }
)

# Common parameters present on most task types in Rails but modeled on
# ``CommonTaskParameters`` — always allow them through.
COMMON_PASS_THROUGH: frozenset[str] = frozenset(
    {
        "strict_variables",
        "disable_validation",
        "delete_payload_paths",
    }
)

# Callout-specific params that Rails stores in parameters; the creative
# pipeline can surface them via ``content_templates``.
CALLOUT_EXTRA_PASS_THROUGH: frozenset[str] = frozenset(
    {
        "files",
        "form_datas",
        "api_name",
        "api_doc_url",
        "notification_history_enabled",
    }
)


# ---------------------------------------------------------------------------
# Type introspection helpers (cached)
# ---------------------------------------------------------------------------

_TYPE_HINT_CACHE: dict[type, dict[str, Any]] = {}
_BASE_TYPE_CACHE: dict[tuple[str, str], Optional[type]] = {}


def _config_class(action_type: str) -> Optional[type[BaseModel]]:
    return TASK_TYPE_CONFIG_MAP.get(action_type)


def _type_hints_for(cls: type) -> dict[str, Any]:
    """Return cached resolved ``get_type_hints`` for a generated class."""
    if cls in _TYPE_HINT_CACHE:
        return _TYPE_HINT_CACHE[cls]
    try:
        hints = typing.get_type_hints(cls, include_extras=True)
    except Exception:
        hints = {}
    _TYPE_HINT_CACHE[cls] = hints
    return hints


def _base_type(action_type: str, field_name: str) -> Optional[type]:
    """Return the primary concrete type of ``<Action>TaskParameters.<field>``.

    Unwraps ``Annotated`` and ``Optional``/``Union`` to pick the first
    non-``NoneType`` concrete type. Used to drive wire-format decisions
    (stringify dict/list only when the field is typed ``str``; boolean→str
    only when the field is typed ``bool``).
    """
    key = (action_type, field_name)
    if key in _BASE_TYPE_CACHE:
        return _BASE_TYPE_CACHE[key]
    cls = _config_class(action_type)
    if cls is None:
        _BASE_TYPE_CACHE[key] = None
        return None
    annotation = _type_hints_for(cls).get(field_name)
    if annotation is None:
        _BASE_TYPE_CACHE[key] = None
        return None

    stack = [annotation]
    picked: Optional[type] = None
    while stack:
        current = stack.pop()
        origin = typing.get_origin(current)
        args = typing.get_args(current)
        if origin is typing.Annotated and args:
            stack.append(args[0])
            continue
        if origin in (typing.Union, types.UnionType):
            stack.extend(args)
            continue
        if current is type(None):
            continue
        if origin is not None and isinstance(origin, type):
            picked = origin
            break
        if isinstance(current, type):
            picked = current
            break
    _BASE_TYPE_CACHE[key] = picked
    return picked


_NO_DEFAULT = object()


def _pydantic_field_default(field: Any, *, missing: Any = None) -> Any:
    """Return a Pydantic ``FieldInfo`` default (post ``default_factory`` call)
    or ``missing`` when no default is declared."""
    if field is None:
        return missing
    default = getattr(field, "default", PydanticUndefined)
    if default is not PydanticUndefined:
        return default
    factory = getattr(field, "default_factory", None)
    if factory is not None:
        try:
            return factory()
        except Exception:
            return missing
    return missing


def _field_default(action_type: str, field_name: str, *, missing: Any = None) -> Any:
    """Return the Pydantic model default for ``<Action>TaskParameters.<field>``.

    Backwards-compatible: when no default is declared the legacy behavior is
    to return ``None``. Callers that need to distinguish "no default" from
    "declared default of None / ``[]`` / ``''``" should pass
    ``missing=_NO_DEFAULT`` (module-local sentinel).
    """
    cls = _config_class(action_type)
    if cls is None:
        return missing
    return _pydantic_field_default(cls.model_fields.get(field_name), missing=missing)


# ---------------------------------------------------------------------------
# Schema-driven required-field resolution
# ---------------------------------------------------------------------------
#
# The manifest's per-task parameters schema is the single source of truth for
# which fields must appear in the final JSON. We resolve two sets per task:
#
# 1. Unconditional ``required`` — listed at the top of the parameters schema
#    (e.g. Callout's ``["url", "method", "body_type", "headers", "retry_rules"]``).
# 2. Conditional ``allOf[{if, then}]`` clauses — their ``then.required`` is
#    added when the ``if.properties`` predicate holds for the current params
#    (e.g. ``body_type == "raw"`` → add ``raw_body``; ``authorization.type ==
#    "basic_auth"`` → hydrate ``username``/``password`` inside the
#    ``authorization`` sub-dict).
#
# Only fields in the resolved required set are hydrated from Pydantic defaults.
# Everything else is left exactly as the agent set it (or omitted).


_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"
_MANIFEST_CACHE: Optional[dict[str, Any]] = None
_REQUIRED_SCHEMA_CACHE: dict[str, tuple[set[str], list[dict[str, Any]]]] = {}


def _load_manifest() -> dict[str, Any]:
    """Load ``manifest.json`` once and cache it module-locally."""
    global _MANIFEST_CACHE
    if _MANIFEST_CACHE is None:
        _MANIFEST_CACHE = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    return _MANIFEST_CACHE


def _resolve_schema_ref(manifest: dict[str, Any], node: Any) -> Any:
    """Follow ``$ref`` chains pointing into ``#/$defs/...`` until we hit a
    non-ref node. Non-dict inputs and unknown refs are returned unchanged."""
    seen: set[str] = set()
    while isinstance(node, dict) and "$ref" in node:
        ref = node["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/$defs/") or ref in seen:
            return node
        seen.add(ref)
        key = ref[len("#/$defs/") :]
        next_node = manifest.get("$defs", {}).get(key)
        if next_node is None:
            return node
        node = next_node
    return node


def _collect_parameters_schema(
    manifest: dict[str, Any], action_schema: dict[str, Any]
) -> dict[str, Any]:
    """Return a merged parameters schema dict: ``{"required": [...],
    "allOf": [...conditional clauses...]}``.

    Walks the action schema's ``allOf`` chain (resolving ``$ref`` links),
    collects every ``properties.parameters`` node it finds, then walks each
    parameters node's own ``allOf`` chain to gather both the unconditional
    ``required`` list(s) and any ``if/then`` conditional clauses.
    """
    merged_required: list[str] = []
    merged_conditionals: list[dict[str, Any]] = []
    params_stack: list[Any] = []

    action_stack: list[Any] = [action_schema]
    seen_action_ids: set[int] = set()
    while action_stack:
        node = _resolve_schema_ref(manifest, action_stack.pop())
        if not isinstance(node, dict) or id(node) in seen_action_ids:
            continue
        seen_action_ids.add(id(node))
        props = node.get("properties") if isinstance(node.get("properties"), dict) else None
        if props is not None:
            params_node = props.get("parameters")
            if isinstance(params_node, dict):
                params_stack.append(params_node)
        for sub in node.get("allOf") or []:
            action_stack.append(sub)

    seen_params_ids: set[int] = set()
    while params_stack:
        params_node = _resolve_schema_ref(manifest, params_stack.pop())
        if not isinstance(params_node, dict) or id(params_node) in seen_params_ids:
            continue
        seen_params_ids.add(id(params_node))
        req = params_node.get("required")
        if isinstance(req, list):
            merged_required.extend(str(r) for r in req)
        for sub in params_node.get("allOf") or []:
            resolved = _resolve_schema_ref(manifest, sub)
            if isinstance(resolved, dict):
                if resolved.get("if") is not None and resolved.get("then") is not None:
                    merged_conditionals.append(resolved)
                else:
                    params_stack.append(resolved)

    return {"required": merged_required, "allOf": merged_conditionals}


def _required_and_conditionals(
    action_type: str,
) -> tuple[set[str], list[dict[str, Any]]]:
    """Return ``(unconditional_required_set, [conditional_if_then_clauses])``
    for ``action_type``, caching the result."""
    if action_type in _REQUIRED_SCHEMA_CACHE:
        return _REQUIRED_SCHEMA_CACHE[action_type]
    manifest = _load_manifest()
    schema_key = (manifest.get("x-task-index") or {}).get("mapping", {}).get(action_type)
    if not schema_key:
        _REQUIRED_SCHEMA_CACHE[action_type] = (set(), [])
        return _REQUIRED_SCHEMA_CACHE[action_type]
    action_schema = manifest.get("$defs", {}).get(schema_key)
    if not isinstance(action_schema, dict):
        _REQUIRED_SCHEMA_CACHE[action_type] = (set(), [])
        return _REQUIRED_SCHEMA_CACHE[action_type]
    merged = _collect_parameters_schema(manifest, action_schema)
    unconditional = set(merged["required"])
    conditionals = list(merged["allOf"])
    _REQUIRED_SCHEMA_CACHE[action_type] = (unconditional, conditionals)
    return _REQUIRED_SCHEMA_CACHE[action_type]


def _eval_if_predicate(if_clause: dict[str, Any], params: dict[str, Any]) -> bool:
    """Return ``True`` iff every ``properties.<k>`` constraint in ``if_clause``
    holds against ``params``.

    Supports ``const`` / ``enum`` scalar constraints and one level of nested
    ``properties`` (e.g. ``authorization.type == "basic_auth"``).
    """
    props = if_clause.get("properties")
    if not isinstance(props, dict):
        return True
    for key, spec in props.items():
        if key not in params:
            return False
        value = params[key]
        if not isinstance(spec, dict):
            continue
        if "const" in spec and value != spec["const"]:
            return False
        if "enum" in spec and value not in spec["enum"]:
            return False
        nested = spec.get("properties")
        if isinstance(nested, dict):
            if not isinstance(value, dict):
                return False
            for sub_key, sub_spec in nested.items():
                if sub_key not in value:
                    return False
                if not isinstance(sub_spec, dict):
                    continue
                sub_value = value[sub_key]
                if "const" in sub_spec and sub_value != sub_spec["const"]:
                    return False
                if "enum" in sub_spec and sub_value not in sub_spec["enum"]:
                    return False
    return True


def _resolve_required_for_params(
    action_type: str, params: dict[str, Any]
) -> tuple[set[str], dict[str, set[str]]]:
    """Return ``(top_level_required, nested_required_by_parent)`` evaluated
    against the current ``params`` state.

    ``nested_required_by_parent`` maps a parent dict field (e.g.
    ``"authorization"``) to the set of sub-field names that must appear inside
    it when a conditional ``then.properties.<parent>.required`` fires.
    """
    unconditional, conditionals = _required_and_conditionals(action_type)
    top: set[str] = set(unconditional)
    nested: dict[str, set[str]] = {}
    for clause in conditionals:
        if not _eval_if_predicate(clause.get("if") or {}, params):
            continue
        then = clause.get("then") or {}
        for req in then.get("required") or []:
            top.add(str(req))
        for parent_key, parent_spec in (then.get("properties") or {}).items():
            if not isinstance(parent_spec, dict):
                continue
            sub_required = parent_spec.get("required")
            if isinstance(sub_required, list) and sub_required:
                nested.setdefault(parent_key, set()).update(str(r) for r in sub_required)
    return top, nested


def _nested_model_cls(field: Any) -> Optional[type[BaseModel]]:
    """Return the ``BaseModel`` subclass declared by a Pydantic field's
    annotation, unwrapping ``Annotated`` / ``Optional`` / ``Union``.
    Returns ``None`` for non-model fields.
    """
    if field is None:
        return None
    stack: list[Any] = [field.annotation]
    while stack:
        current = stack.pop()
        origin = typing.get_origin(current)
        args = typing.get_args(current)
        if origin is typing.Annotated and args:
            stack.append(args[0])
            continue
        if origin in (typing.Union, types.UnionType):
            stack.extend(args)
            continue
        if current is type(None):
            continue
        if isinstance(current, type) and issubclass(current, BaseModel):
            return current
    return None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class TaskTemplateEngine:
    """Produce correct task JSON from a plan task config using the Pydantic
    ``<Action>TaskParameters`` model plus the manifest schema as sources of
    truth.

    Responsibilities:
    1. Parameter whitelist — only fields declared on the model + common/callout
       pass-throughs survive.
    2. Value conversion — ``bool → "true"/"false"``; dict/list stringified when
       the field is typed ``str``.
    3. Nesting — auto-wrap flat amendment/invoice fields under their wrapper.
    4. Schema-required hydration — fill missing ``required`` fields
       (unconditional + conditional ``if/then``) with their Pydantic defaults.
    5. Post-assembly prune (see ``assembler._prune_default_and_empty_parameters``)
       drops non-required keys that are empty or equal to the Pydantic default.
    """

    def __init__(self) -> None:
        self._allowed_cache: dict[str, set[str]] = {}

    def allowed_params(self, action_type: str) -> Optional[set[str]]:
        """Return the set of parameter names declared on ``<Action>TaskParameters``."""
        if action_type in self._allowed_cache:
            return self._allowed_cache[action_type]
        cls = _config_class(action_type)
        if cls is None:
            return None
        allowed = set(cls.model_fields.keys())
        self._allowed_cache[action_type] = allowed
        return allowed

    def generate_task(
        self,
        task_id: int,
        name: str,
        action_type: str,
        config: dict,
        css: dict[str, str],
        priority: str = "Medium",
    ) -> dict:
        """Produce a complete task JSON dict from a plan task config.

        Schema-``required`` fields (unconditional + conditional ``if/then``)
        are hydrated into ``parameters`` from their Pydantic defaults when the
        agent omitted them. Non-required optional fields are left untouched
        here; a follow-up prune drops any that remain at their default.
        """
        allowed = self.allowed_params(action_type) or set()
        raw_params = dict(config.get("parameters") or {})

        self._wrap_flat_fields(action_type, raw_params)

        filtered: dict[str, Any] = {}
        for key, value in raw_params.items():
            if key in allowed:
                filtered[key] = self._convert_value(value, _base_type(action_type, key))

        pass_keys = COMMON_PASS_THROUGH
        if action_type in ("Callout", "AsynchronousCallout"):
            pass_keys = pass_keys | CALLOUT_EXTRA_PASS_THROUGH
        for key in pass_keys:
            if key in raw_params and key not in filtered:
                filtered[key] = self._convert_value(raw_params[key], None)

        if action_type == "Iterate":
            iterate_obj = filtered.pop("object", None)
        else:
            iterate_obj = None

        self._hydrate_required_fields(action_type, filtered)

        task_object = config.get("object")
        if action_type == "Iterate" and not task_object and iterate_obj:
            task_object = iterate_obj

        task: dict[str, Any] = {
            "id": task_id,
            "name": name,
            "action_type": action_type,
            "object": task_object,
            "object_id": config.get("object_id"),
            "call_type": "REST" if action_type in REST_ONLY_TASK_TYPES else "SOAP",
            "css": css,
            "task_id": config.get("task_id"),
            "concurrent_limit": self._concurrent_limit(action_type),
            "priority": priority,
            "tags": list(config.get("tags") or []),
            "assignment": [],
            "entity_id": None,
            "zuora_org_id": None,
            "zuora_org_ids": [],
            "subprocess_id": None,
            "parameters": filtered,
        }
        return task

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _wrap_flat_fields(action_type: str, params: dict) -> None:
        """If the task type expects ``fields.<Wrapper>.<Key>``, wrap flat keys
        under the wrapper when they aren't already."""
        entry = FLAT_FIELDS_WRAPPER.get(action_type)
        if not entry:
            return
        wrapper_key, flat_keys = entry
        fields = params.get("fields")
        if not isinstance(fields, dict) or not fields:
            return
        if wrapper_key in fields:
            return
        if not flat_keys.intersection(fields.keys()):
            return
        params["fields"] = {wrapper_key: dict(fields)}

    @staticmethod
    def _convert_value(value: Any, base_type: Optional[type]) -> Any:
        """Convert a plan value to the Rails wire format.

        ``base_type`` is the primary concrete type of the corresponding
        Pydantic field (from ``_base_type``). When ``None`` (pass-through
        params or nested conversion), only generic boolean coercion applies.
        """
        if value is None:
            return None
        if isinstance(value, bool):
            return "true" if value else "false"
        if base_type is str:
            if isinstance(value, (dict, list)):
                return json.dumps(value)
            if isinstance(value, int):
                return str(value)
            return value
        if isinstance(value, dict):
            return {k: TaskTemplateEngine._convert_value(v, None) for k, v in value.items()}
        if isinstance(value, list):
            return [TaskTemplateEngine._convert_value(v, None) for v in value]
        return value

    @staticmethod
    def _default_on_wire(default: Any) -> Any:
        """Convert a Pydantic default to the form it appears as after wire conversion."""
        if default is None:
            return None
        if isinstance(default, bool):
            return "true" if default else "false"
        return default

    @staticmethod
    def _fallback_empty_for_field(field: Any) -> Any:
        """Best-effort empty value for a field whose Pydantic default is
        ``None`` but which the schema marks required.

        The generated Pydantic fields for string sub-properties without an
        explicit JSON-schema default still get ``= None``. When that field
        becomes conditionally required (e.g. ``authorization.username`` when
        ``authorization.type == "basic_auth"``), we want ``""`` on the wire,
        not ``None``, so the field is visible in the JSON and validators can
        flag it if left empty.
        """
        annotation = getattr(field, "annotation", None)
        stack: list[Any] = [annotation]
        candidates: list[Any] = []
        while stack:
            current = stack.pop()
            origin = typing.get_origin(current)
            args = typing.get_args(current)
            if origin is typing.Annotated and args:
                stack.append(args[0])
                continue
            if origin in (typing.Union, types.UnionType):
                stack.extend(args)
                continue
            if current is type(None) or current is None:
                continue
            candidates.append(current)
        for base in candidates:
            origin = typing.get_origin(base)
            if base is str:
                return ""
            if base is bool:
                return "false"
            if origin is list or base is list:
                return []
            if origin is dict or base is dict:
                return {}
        return ""

    @classmethod
    def _prune_defaults(cls, action_type: str, params: dict) -> None:
        """Drop params that are empty or equal to their model default.

        .. deprecated::
            Retained for backwards compatibility with callers that still want
            the minimized parameter shape. The default pipeline now uses
            :meth:`_hydrate_defaults` so every declared field is preserved.
        """
        to_drop: list[str] = []
        for key, value in params.items():
            if (action_type, key) in KEEP_EVEN_IF_DEFAULT:
                continue
            default_raw = _field_default(action_type, key)
            if default_raw is not None:
                default_wire = cls._default_on_wire(default_raw)
                if value == default_wire:
                    to_drop.append(key)
                    continue
            if value is None or value == "" or value == "''":
                to_drop.append(key)
            elif isinstance(value, (list, dict)) and len(value) == 0:
                to_drop.append(key)
            elif key == "strict_variables" and value in (True, "true"):
                to_drop.append(key)
            elif key == "disable_validation" and value in (False, "false"):
                to_drop.append(key)
        for key in to_drop:
            del params[key]
        _recursive_prune_empty(params)

    @classmethod
    def _hydrate_required_fields(cls, action_type: str, params: dict) -> None:
        """Fill every schema-``required`` field the agent omitted with its
        Pydantic default.

        "Required" here comes from the manifest's parameters schema:

        * unconditional ``required`` (e.g. Callout's
          ``["url", "method", "body_type", "headers", "retry_rules"]``);
        * conditional ``allOf[{if, then}].then.required`` whose ``if``
          predicate holds for the current params (e.g. ``raw_body`` when
          ``body_type == "raw"``);
        * nested ``then.properties.<parent>.required`` applied inside the
          corresponding sub-dict (e.g. ``username`` / ``password`` inside
          ``authorization`` when ``authorization.type == "basic_auth"``).

        Hydration runs in a fixed-point loop: a newly-hydrated value (e.g.
        ``body_type = "raw"``) can make another conditional clause fire
        (``raw_body`` now required), so we re-resolve until the required set
        stops growing.

        Non-required optional fields are left exactly as the agent set them
        (or omitted) so the final JSON stays compact. Booleans are
        wire-converted via :meth:`_default_on_wire` (``True`` -> ``"true"``).
        """
        config_cls = _config_class(action_type)
        if config_cls is None:
            return

        for _ in range(4):
            top_required, nested_required = _resolve_required_for_params(action_type, params)
            mutated = False
            for key in top_required:
                if key in params:
                    continue
                if key not in config_cls.model_fields:
                    continue
                default = _field_default(action_type, key, missing=_NO_DEFAULT)
                if default is _NO_DEFAULT:
                    continue
                params[key] = cls._default_on_wire(default)
                mutated = True

            for parent_key, sub_keys in nested_required.items():
                parent_field = config_cls.model_fields.get(parent_key)
                if parent_field is None:
                    continue
                sub_cls = _nested_model_cls(parent_field)
                if sub_cls is None:
                    continue
                parent_value = params.get(parent_key)
                if parent_value is None:
                    parent_default = _pydantic_field_default(parent_field, missing=_NO_DEFAULT)
                    if parent_default is _NO_DEFAULT or parent_default is None:
                        parent_value = {}
                    elif isinstance(parent_default, dict):
                        parent_value = dict(parent_default)
                    elif hasattr(parent_default, "model_dump"):
                        parent_value = parent_default.model_dump()
                    else:
                        parent_value = {}
                    params[parent_key] = parent_value
                    mutated = True
                if not isinstance(parent_value, dict):
                    continue
                for sub_key in sub_keys:
                    if sub_key in parent_value and parent_value[sub_key] is not None:
                        continue
                    sub_field = sub_cls.model_fields.get(sub_key)
                    if sub_field is None:
                        continue
                    sub_default = _pydantic_field_default(sub_field, missing=_NO_DEFAULT)
                    if sub_default is _NO_DEFAULT:
                        sub_default = cls._fallback_empty_for_field(sub_field)
                    wire_value = cls._default_on_wire(sub_default)
                    if wire_value is None:
                        wire_value = cls._fallback_empty_for_field(sub_field)
                    parent_value[sub_key] = wire_value
                    mutated = True

            if not mutated:
                break

    @staticmethod
    def _concurrent_limit(action_type: str) -> int:
        if action_type == "Export":
            return 5
        if action_type == "Iterate":
            return 500
        return 9999999


def _recursive_prune_empty(obj: Any) -> None:
    """In-place remove keys with None, empty string, or empty dict/list."""
    if not isinstance(obj, dict):
        return
    to_drop: list[str] = []
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
