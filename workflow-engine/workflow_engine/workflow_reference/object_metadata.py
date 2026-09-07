"""Runtime-first Zuora object metadata resolver.

``get_object_metadata(name, tool_context)`` is the single entry point every
caller (plan validator, generate_workflow field filter, lookup_zuora_schema,
etc.) should use when it needs schema for a Zuora object.  The resolver
enforces the canonical priority order:

1. Live ``GET /v1/describe/{object}?showRelationships=true`` XML.
2. Cached JSON at ``knowledge_base/objects/<Object>.json``.
3. Compact markdown fallback
   (``knowledge_base/zuora_objects_and_fields.md`` +
   ``knowledge_base/zuora_objects_relationships.md``).

Results are memoized on the **session** ``invocation_state`` under
``_object_metadata_cache`` so repeated lookups inside a single agent turn
don't thrash the live API.  Cache keys are tuples of
``(tenant_id, entity_ids, object_name_lowercased)``.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import structlog

try:
    import httpx
except ImportError:  # pragma: no cover - optional for offline coding-agent use
    httpx = None  # type: ignore[assignment]

try:
    from tools._http import _build_zuora_headers, _get_bearer_token
except ImportError:  # coding-agent plugin: use env-backed HTTP client
    try:
        from workflow_engine.zuora_http import _build_zuora_headers, _get_bearer_token
    except ImportError:
        _build_zuora_headers = None  # type: ignore[assignment,misc]
        _get_bearer_token = None  # type: ignore[assignment,misc]
from workflow_engine.workflow_reference.describe_parser import (
    FieldInfo,
    ObjectDescribe,
    RelatedObject,
    infer_foreign_key_field,
    parse_object_describe,
)

logger = structlog.get_logger(__name__)

_DESCRIBE_TIMEOUT_S = 15.0
_STATE_CACHE_KEY = "_object_metadata_cache"
_STATE_CACHE_LOCK_KEY = "_object_metadata_cache_lock"

_KB_ROOT = Path(__file__).resolve().parent.parent / "knowledge_base"
_KB_OBJECTS_DIR = _KB_ROOT / "objects"
_KB_FIELDS_MD = _KB_ROOT / "zuora_objects_and_fields.md"
_KB_RELS_MD = _KB_ROOT / "zuora_objects_relationships.md"


__all__ = [
    "ObjectMetadataResult",
    "get_object_metadata",
    "build_relationships_graph",
    "collect_object_names_from_plan",
    "canonicalize_object_name",
    "clear_cache",
]


# ---------------------------------------------------------------------------
# Canonical-name index (alias / event -> describable type)
# ---------------------------------------------------------------------------
#
# Zuora's ``/v1/describe`` catalog only contains *schema types* like
# ``Contact`` and ``PaymentMethod``.  Plans commonly mention navigation
# aliases (``BillToContact``, ``DefaultPaymentMethod``) or event names
# (``BillingRunCompletion``) - both of which 404 against the describe API.
#
# To avoid wasted API calls and misleading 404 warnings, every name routed
# through :func:`get_object_metadata` first passes through
# :func:`canonicalize_object_name`, which maps:
#
# * event names (``BillingRunCompletion`` -> ``BillingRun``) using
#   :data:`~tools.workflow_reference.event_parameters.EVENT_BASE_OBJECTS`;
# * relationship aliases (``BillToContact`` -> ``Contact``,
#   ``ParentAccount`` -> ``Account``) by inspecting the
#   ``<related-objects>`` entries in the local JSON cache (the href tail
#   is the authoritative describable type).
#
# The maps are populated lazily on first call so tests can monkeypatch
# ``_KB_OBJECTS_DIR`` before anything is cached.

_CANONICAL_BY_LOWER: dict[str, str] = {}
_ALIAS_BY_LOWER: dict[str, str] = {}
_NAME_INDEX_READY = False


def _ensure_name_index() -> None:
    """Populate ``_CANONICAL_BY_LOWER`` / ``_ALIAS_BY_LOWER`` from the cache.

    Idempotent: subsequent calls are a no-op until
    :func:`clear_name_index` is invoked.
    """
    global _NAME_INDEX_READY
    if _NAME_INDEX_READY:
        return
    _CANONICAL_BY_LOWER.clear()
    _ALIAS_BY_LOWER.clear()

    if _KB_OBJECTS_DIR.exists():
        for path in sorted(_KB_OBJECTS_DIR.glob("*.json")):
            if path.name.startswith("_"):
                continue
            _CANONICAL_BY_LOWER[path.stem.lower()] = path.stem

        for path in sorted(_KB_OBJECTS_DIR.glob("*.json")):
            if path.name.startswith("_"):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for rel in data.get("related_objects") or []:
                if not isinstance(rel, dict):
                    continue
                alias = rel.get("name")
                href = rel.get("href") or ""
                if not isinstance(alias, str) or not alias:
                    continue
                target_tail = href.rstrip("/").rsplit("/", 1)[-1] if href else ""
                target = (
                    _CANONICAL_BY_LOWER.get(
                        target_tail.lower(),
                    )
                    or target_tail
                    or None
                )
                if not target:
                    continue
                alias_lower = alias.lower()
                if alias_lower in _CANONICAL_BY_LOWER:
                    continue  # alias happens to match a real type name
                _ALIAS_BY_LOWER.setdefault(alias_lower, target)

    _NAME_INDEX_READY = True


def clear_name_index() -> None:
    """Drop the cached name index; primarily used by tests."""
    global _NAME_INDEX_READY
    _NAME_INDEX_READY = False
    _CANONICAL_BY_LOWER.clear()
    _ALIAS_BY_LOWER.clear()


def canonicalize_object_name(name: str) -> tuple[str | None, str]:
    """Resolve ``name`` to its describable Zuora object type.

    Returns ``(canonical, reason)`` where ``reason`` is one of:

    * ``"catalog"`` - ``name`` already is a canonical type.
    * ``"alias"`` - ``name`` is a navigation alias (e.g. ``BillToContact``)
      that maps to the returned type (``Contact``).
    * ``"event"`` - ``name`` is an event (e.g. ``BillingRunCompletion``)
      that maps to the event's base describable object (``BillingRun``).
      If the base object is itself undescribable, ``canonical`` is ``None``.
    * ``"unknown"`` - ``name`` is not in the catalog or alias map; returned
      verbatim so the live API still gets a chance.
    * ``"empty"`` - ``name`` is blank.
    """
    raw = (name or "").strip()
    if not raw:
        return None, "empty"
    _ensure_name_index()

    # Event names first: they never describe directly, but their base
    # object often does. Recursively canonicalize the base object.
    try:
        from workflow_engine.workflow_reference.event_parameters import EVENT_BASE_OBJECTS
    except Exception:
        EVENT_BASE_OBJECTS = {}  # type: ignore[assignment]  # noqa: N806

    if raw in EVENT_BASE_OBJECTS:
        base, _ = EVENT_BASE_OBJECTS[raw]
        if not base or base == raw:
            return None, "event"
        canonical, _ = canonicalize_object_name(base)
        return canonical, "event"

    low = raw.lower()
    if low in _CANONICAL_BY_LOWER:
        return _CANONICAL_BY_LOWER[low], "catalog"
    if low in _ALIAS_BY_LOWER:
        return _ALIAS_BY_LOWER[low], "alias"
    return raw, "unknown"


@dataclass(frozen=True)
class ObjectMetadataResult:
    """Outcome of a resolver call.

    ``describe`` is ``None`` when none of the three sources had the object.
    ``source`` is one of ``"api"`` / ``"json"`` / ``"markdown"`` / ``"none"``.
    """

    describe: ObjectDescribe | None
    source: str
    error: str | None = None

    @property
    def is_authoritative(self) -> bool:
        """True when the result came from the live describe or JSON cache.

        Callers that need strict flags (e.g. ``contexts`` for Export) should
        only trust authoritative results; the MD fallback lacks flag data.
        """
        return self.source in {"api", "json"}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def get_object_metadata(
    object_name: str,
    tool_context: Any,
    *,
    refresh: bool = False,
) -> ObjectMetadataResult:
    """Return :class:`ObjectMetadataResult` for ``object_name``.

    Args:
        object_name: The Zuora object name (case-insensitive).
        tool_context: The Strands ``ToolContext`` (or any object exposing an
            ``invocation_state`` dict; pass ``None`` to skip session caching
            and always round-trip to the live endpoint).
        refresh: When ``True``, bypass the session cache.
    """
    canonical, reason = canonicalize_object_name(object_name)
    if canonical is None:
        return ObjectMetadataResult(
            describe=None,
            source="none",
            error=(f"{object_name!r} is not a describable Zuora object " f"(reason={reason})"),
        )
    normalized = canonical

    state = _state(tool_context)
    cache_key = _cache_key(state, normalized)

    if state is not None and not refresh:
        cache = state.get(_STATE_CACHE_KEY)
        if isinstance(cache, dict):
            cached = cache.get(cache_key)
            if isinstance(cached, ObjectMetadataResult):
                return cached

    lock = _lock(state)
    if lock is not None:
        async with lock:
            if state is not None and not refresh:
                cache = state.get(_STATE_CACHE_KEY)
                if isinstance(cache, dict):
                    cached = cache.get(cache_key)
                    if isinstance(cached, ObjectMetadataResult):
                        return cached
            result = await _fetch(normalized, state)
            _store(state, cache_key, result)
            return result

    result = await _fetch(normalized, state)
    _store(state, cache_key, result)
    return result


def clear_cache(tool_context: Any) -> None:
    """Remove every cached resolver entry on the given session."""
    state = _state(tool_context)
    if state is None:
        return
    state.pop(_STATE_CACHE_KEY, None)
    state.pop(_STATE_CACHE_LOCK_KEY, None)


# ---------------------------------------------------------------------------
# Plan-level helpers: collect objects + build legacy relationships graph
# ---------------------------------------------------------------------------


def collect_object_names_from_plan(plan: dict[str, Any]) -> list[str]:
    """Return the deduped list of object names referenced by a plan.

    Looks at every task's top-level ``object``, ``parameters.object``, and
    ``parameters.fields`` keys; also harvests objects referenced via
    ``Data.<Object>.<Field>`` Liquid paths in string parameter values.

    Event names appearing in ``trigger.event_names`` are translated to
    their base describable object (e.g. ``BillingRunCompletion`` ->
    ``BillingRun``) via :data:`EVENT_BASE_OBJECTS`, since event names
    themselves are not describable types and would 404 against /describe.

    Order is preserved so the first occurrence wins for diagnostics.
    """
    seen: dict[str, None] = {}

    def _add(name: Any) -> None:
        if not isinstance(name, str):
            return
        stripped = name.split("__")[0].split(".")[0].strip()
        if stripped and stripped[0].isalpha():
            seen.setdefault(stripped, None)

    for task in plan.get("tasks") or []:
        if not isinstance(task, dict):
            continue
        _add(task.get("object"))
        params = task.get("parameters") or {}
        if not isinstance(params, dict):
            continue
        _add(params.get("object"))
        fields = params.get("fields")
        if isinstance(fields, dict):
            for key in fields.keys():
                _add(key)
        for value in _walk_strings(params):
            for ref in _LIQUID_DATA_OBJ.findall(value):
                _add(ref)

    try:
        from workflow_engine.workflow_reference.event_parameters import (
            EVENT_BASE_OBJECTS,
            coerce_event_names_list,
        )
    except Exception:
        EVENT_BASE_OBJECTS = {}  # type: ignore[assignment]  # noqa: N806
        coerce_event_names_list = lambda raw: raw if isinstance(raw, list) else []  # type: ignore[assignment,misc]

    trigger = plan.get("trigger") or {}
    for name in coerce_event_names_list(trigger.get("event_names")):
        if isinstance(name, str) and name in EVENT_BASE_OBJECTS:
            base, _ = EVENT_BASE_OBJECTS[name]
            _add(base)
        else:
            _add(name)

    return list(seen.keys())


_LIQUID_DATA_OBJ = re.compile(r"\{\{\s*Data\.([A-Za-z][\w]*)")


def _walk_strings(node: Any) -> Iterator[str]:
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from _walk_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_strings(v)


async def build_relationships_graph(
    plan: dict[str, Any],
    tool_context: Any,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Resolve every object in ``plan`` and build a parent/child graph.

    Returned shape matches the legacy
    ``load_object_relationships()`` output so plan_validator can swap in
    the resolver-backed data without structural changes::

        {
            "Invoice": {
                "references": [
                    {"field": "AccountId", "target_object": "Account",
                     "raw_label": "AccountId -> Account (to_one)",
                     "cardinality": "TO_ONE"},
                    ...
                ],
                "referenced_by": [
                    {"source_object": "InvoiceItem", "field": "InvoiceId"},
                    ...
                ],
            },
            ...
        }

    Missing objects / resolver failures are silently omitted; callers should
    treat the graph as best-effort.
    """
    names = collect_object_names_from_plan(plan)
    if not names:
        return {}

    results = await asyncio.gather(
        *(get_object_metadata(n, tool_context) for n in names),
        return_exceptions=True,
    )
    describes: dict[str, ObjectDescribe] = {}
    for name, res in zip(names, results):
        if isinstance(res, BaseException):
            logger.info("object_metadata.plan_resolve_failed", object=name, error=str(res))
            continue
        if res.describe is None:
            continue
        # Key by the describe's own canonical name so aliases (BillToContact)
        # and events (BillingRunCompletion) collapse onto their base type
        # (Contact / BillingRun) instead of creating duplicate graph entries.
        describes[res.describe.name] = res.describe

    return _build_legacy_graph(describes)


def _build_legacy_graph(
    describes: dict[str, ObjectDescribe],
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Translate ObjectDescribe records into the legacy relationships shape."""
    graph: dict[str, dict[str, list[dict[str, Any]]]] = {}

    for name, d in describes.items():
        refs: list[dict[str, Any]] = []
        for rel in d.related_objects:
            if not rel.is_to_one:
                continue
            fk_field = _infer_fk_field(d, rel)
            label = _format_relationship_label(fk_field, rel)
            refs.append(
                {
                    "field": fk_field or rel.name,
                    "target_object": rel.name,
                    "raw_label": label,
                    "cardinality": rel.cardinality,
                    "direct_relationship": rel.direct_relationship,
                    "path": rel.path,
                }
            )
        graph[name] = {
            "references": refs,
            "referenced_by": [],
        }

    for parent_name, parent_desc in describes.items():
        for rel in parent_desc.related_objects:
            if not rel.is_to_many:
                continue
            child = rel.name
            if child not in graph:
                graph[child] = {"references": [], "referenced_by": []}
            fk_guess = _guess_child_fk(parent_desc, rel, describes.get(child))
            graph[child]["referenced_by"].append(
                {
                    "source_object": parent_name,
                    "field": fk_guess,
                    "cardinality": rel.cardinality,
                    "path": rel.path,
                }
            )

    for src_name, src_rel in graph.items():
        for ref in src_rel["references"]:
            target = ref["target_object"]
            if target in graph and target != src_name:
                # Avoid dup entries if we already appended the TO_MANY side.
                existing = graph[target]["referenced_by"]
                if not any(
                    e.get("source_object") == src_name and e.get("field") == ref["field"]
                    for e in existing
                ):
                    existing.append(
                        {
                            "source_object": src_name,
                            "field": ref["field"],
                        }
                    )

    return graph


def _infer_fk_field(parent: ObjectDescribe, rel: RelatedObject) -> str | None:
    """Guess the FK column on ``parent`` pointing at ``rel``.

    Thin wrapper around :func:`describe_parser.infer_foreign_key_field` that
    adapts the relation-first call signature used throughout this module.
    """
    return infer_foreign_key_field(parent, rel.name)


def _guess_child_fk(
    parent: ObjectDescribe,
    rel: RelatedObject,
    child: ObjectDescribe | None,
) -> str | None:
    """For TO_MANY entries, infer the FK column on the *child* side."""
    if child is None:
        return f"{parent.name}Id"
    candidates = (
        f"{parent.name}Id",
        f"{parent.name}ID",
    )
    for candidate in candidates:
        if child.field_by_name(candidate) is not None:
            return candidate
    return candidates[0]


def _format_relationship_label(
    fk_field: str | None,
    rel: RelatedObject,
) -> str:
    cardinality = (rel.cardinality or "").lower().replace("_", "-")
    prefix = fk_field or rel.name
    suffix = f" ({cardinality})" if cardinality else ""
    return f"{prefix} -> {rel.name}{suffix}"


# ---------------------------------------------------------------------------
# Internal: fetch chain
# ---------------------------------------------------------------------------


async def _fetch(
    object_name: str,
    state: dict[str, Any] | None,
) -> ObjectMetadataResult:
    api_result = await _try_api(object_name, state)
    if api_result is not None:
        return api_result

    cached = _load_cached_describe(object_name)
    if cached is not None:
        return ObjectMetadataResult(describe=cached, source="json")

    md_fields = _lookup_fields_in_markdown(object_name)
    md_related = _lookup_relationships_in_markdown(object_name)
    if md_fields or md_related:
        synthesized = _synthesize_describe_from_markdown(
            object_name,
            md_fields or [],
            md_related or [],
        )
        return ObjectMetadataResult(describe=synthesized, source="markdown")

    return ObjectMetadataResult(
        describe=None,
        source="none",
        error=f"No schema available for {object_name!r}",
    )


def _has_usable_credentials(config: Any, state: dict[str, Any] | None) -> bool:
    """True when an OAuth token can plausibly be issued for this session."""
    if state is not None:
        sid = state.get("zuora_client_id")
        ssecret = state.get("zuora_client_secret")
        if sid and ssecret:
            return True
    if config is None:
        return False
    try:
        creds = config.zuora.get_creds(require=False)
    except Exception:
        return False
    return bool(creds.client_id and creds.client_secret)


async def _try_api(
    object_name: str,
    state: dict[str, Any] | None,
) -> ObjectMetadataResult | None:
    if state is None:
        return None

    # Coding-agent env session (no Strands config object).
    if (
        _get_bearer_token is not None
        and state.get("zuora_client_id")
        and state.get("zuora_client_secret")
        and state.get("config") is None
    ):
        try:
            from workflow_engine.zuora_http import fetch_object_describe

            return await fetch_object_describe(object_name, state)
        except Exception as exc:
            logger.info(
                "object_metadata.env_api_failed",
                object_name=object_name,
                error=str(exc),
            )
            return None

    if _get_bearer_token is None or httpx is None:
        return None
    config = state.get("config")
    if config is None:
        return None

    # Skip the live API entirely when this deployment has no usable
    # OAuth credentials. We must NOT let the bearer-token helper raise
    # here — the only reason ``_try_api`` returning ``None`` matters is
    # so the caller (``_fetch``) advances to the cached-JSON / markdown
    # tiers. A propagating exception would skip those entirely and the
    # tool would respond with a misleading "Object 'X' not found".
    if not _has_usable_credentials(config, state):
        logger.info(
            "object_metadata.api_skipped_no_credentials",
            object_name=object_name,
        )
        return None

    entity_ids = state.get("entity_ids")
    zuora_version = state.get("zuora_version")
    user_id = state.get("user_id")

    try:
        token = await _get_bearer_token(config, state)
        headers = _build_zuora_headers(
            entity_ids=entity_ids,
            zuora_version=zuora_version,
            bearer_token=token,
            user_id=user_id,
            state=state,
        )
        headers["Accept"] = "application/xml"
        base_url = state.get("zuora_base_url") or config.zuora.base_url
        url = f"{base_url}/v1/describe/{object_name}?showRelationships=true"

        async with httpx.AsyncClient(timeout=_DESCRIBE_TIMEOUT_S) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        return ObjectMetadataResult(
            describe=parse_object_describe(resp.text),
            source="api",
        )
    except Exception as exc:
        # Catch broadly (was: ``httpx.HTTPError, DescribeParseError,
        # OSError, ValueError``) so any unexpected error — credential
        # races, DNS hiccups, malformed responses, transport errors —
        # falls through to the cached-JSON / markdown fallback rather
        # than killing the resolver. The only thing we lose is a more
        # specific log type, which the structured ``error`` field
        # already captures.
        logger.info(
            "object_metadata.api_failed",
            object_name=object_name,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return None


# ---------------------------------------------------------------------------
# Internal: cache helpers
# ---------------------------------------------------------------------------


def _state(tool_context: Any) -> dict[str, Any] | None:
    if tool_context is None:
        return None
    state = getattr(tool_context, "invocation_state", None)
    return state if isinstance(state, dict) else None


def _cache_key(state: dict[str, Any] | None, object_name: str) -> tuple[str, str, str]:
    tenant_id = ""
    entity_ids = ""
    if state is not None:
        tenant_id = str(state.get("tenant_id") or "")
        entity_ids = str(state.get("entity_ids") or "")
    return (tenant_id, entity_ids, object_name.lower())


def _store(
    state: dict[str, Any] | None,
    key: tuple[str, str, str],
    result: ObjectMetadataResult,
) -> None:
    if state is None:
        return
    cache = state.get(_STATE_CACHE_KEY)
    if not isinstance(cache, dict):
        cache = {}
        state[_STATE_CACHE_KEY] = cache
    cache[key] = result


def _lock(state: dict[str, Any] | None) -> asyncio.Lock | None:
    if state is None:
        return None
    lock = state.get(_STATE_CACHE_LOCK_KEY)
    if isinstance(lock, asyncio.Lock):
        return lock
    lock = asyncio.Lock()
    state[_STATE_CACHE_LOCK_KEY] = lock
    return lock


# ---------------------------------------------------------------------------
# Internal: JSON cache
# ---------------------------------------------------------------------------


def _load_cached_describe(object_name: str) -> ObjectDescribe | None:
    if not _KB_OBJECTS_DIR.exists():
        return None

    target_lc = object_name.lower()
    for path in _KB_OBJECTS_DIR.glob("*.json"):
        if path.stem.lower() != target_lc:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                "object_metadata.cache_parse_failed",
                path=str(path),
                error=str(exc),
            )
            return None
        return _describe_from_dict(data)
    return None


def _describe_from_dict(data: dict[str, Any]) -> ObjectDescribe | None:
    name = data.get("name")
    if not name:
        return None
    fields: list[FieldInfo] = []
    for raw in data.get("fields", []) or []:
        if not isinstance(raw, dict) or not raw.get("name"):
            continue
        fields.append(
            FieldInfo(
                name=raw["name"],
                label=raw.get("label"),
                type=raw.get("type"),
                selectable=bool(raw.get("selectable")),
                createable=bool(raw.get("createable")),
                updateable=bool(raw.get("updateable")),
                filterable=bool(raw.get("filterable")),
                custom=bool(raw.get("custom")),
                required=bool(raw.get("required")),
                maxlength=raw.get("maxlength"),
                options=tuple(raw.get("options") or ()),
                contexts=tuple(raw.get("contexts") or ()),
            ),
        )
    related: list[RelatedObject] = []
    for raw in data.get("related_objects", []) or []:
        if not isinstance(raw, dict) or not raw.get("name"):
            continue
        related.append(
            RelatedObject(
                name=raw["name"],
                label=raw.get("label"),
                cardinality=raw.get("cardinality"),
                direct_relationship=bool(raw.get("direct_relationship")),
                path=raw.get("path"),
                href=raw.get("href"),
            ),
        )
    return ObjectDescribe(
        name=name,
        label=data.get("label"),
        href=data.get("href"),
        fields=tuple(fields),
        related_objects=tuple(related),
    )


# ---------------------------------------------------------------------------
# Internal: markdown fallback
# ---------------------------------------------------------------------------


def _lookup_fields_in_markdown(object_name: str) -> list[str] | None:
    """Return bullet-list field names for ``object_name`` from the MD file."""
    return _section_bullets(_KB_FIELDS_MD, object_name)


def _lookup_relationships_in_markdown(object_name: str) -> list[str] | None:
    """Return bullet-list relationship names for ``object_name``."""
    return _section_bullets(_KB_RELS_MD, object_name)


def _section_bullets(md_path: Path, object_name: str) -> list[str] | None:
    if not md_path.exists():
        return None
    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError:
        return None

    pattern = re.compile(
        rf"^##\s+{re.escape(object_name)}\s*$",
        flags=re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        return None

    tail = text[match.end() :]
    next_heading = re.search(r"^##\s+", tail, flags=re.MULTILINE)
    block = tail[: next_heading.start()] if next_heading else tail

    return [
        line[2:].strip()
        for line in block.splitlines()
        if line.startswith("- ") and line[2:].strip()
    ]


def _synthesize_describe_from_markdown(
    object_name: str,
    field_names: list[str],
    related_names: list[str],
) -> ObjectDescribe:
    """Build a degraded :class:`ObjectDescribe` from the MD fallback.

    ``selectable`` defaults to ``True`` so basic queryability checks pass;
    per-field flags and contexts are unknown and default to ``False`` / empty.
    Callers requiring accurate flag data should treat
    ``result.is_authoritative is False`` as "degraded - trust with caution".
    """
    fields = tuple(FieldInfo(name=n, selectable=True) for n in field_names if n)
    related = tuple(_parse_markdown_relationship(n) for n in related_names if n)
    return ObjectDescribe(
        name=object_name,
        fields=fields,
        related_objects=tuple(r for r in related if r is not None),
    )


# Two markdown shapes are supported because ``zuora_objects_relationships.md``
# may have been generated by either build_docs version:
#
#   New (build_docs.py >= rev_b):
#     ``AccountId -> Account (to-one)``
#     ``BillToContactSnapshotId -> ContactSnapshot (to-one, as BillToContactSnapshot)``
#     ``DefaultPaymentMethod (to-one, type PaymentMethod, via Invoice.Account.DefaultPaymentMethod)``
#
#   Legacy:
#     ``Account (TO_ONE)``
#
_MD_REL_ARROW = re.compile(
    r"""^
    (?P<fk>[A-Za-z0-9_]+)\s*->\s*
    (?P<target>[A-Za-z0-9_]+)
    (?:\s*\((?P<qual>[^)]*)\))?
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)
_MD_REL_PLAIN = re.compile(
    r"""^
    (?P<name>[A-Za-z0-9_]+)
    (?:\s*\((?P<qual>[^)]*)\))?
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)
_MD_QUAL_CARD = re.compile(
    r"\b(TO_ONE|TO_MANY|ONE_TO_ONE|ONE_TO_MANY|MANY_TO_ONE|MANY_TO_MANY|to-one|to-many|one-to-one|one-to-many|many-to-one|many-to-many)\b",
    flags=re.IGNORECASE,
)
_MD_QUAL_ALIAS = re.compile(r"\bas\s+([A-Za-z0-9_]+)", flags=re.IGNORECASE)
_MD_QUAL_VIA = re.compile(r"\bvia\s+([A-Za-z0-9_.]+)", flags=re.IGNORECASE)


def _parse_markdown_relationship(raw: str) -> RelatedObject | None:
    """Parse a single ``- ...`` bullet from the legacy relationships MD."""
    text = raw.strip()
    if not text:
        return None

    arrow = _MD_REL_ARROW.match(text)
    if arrow:
        qual = arrow.group("qual") or ""
        alias_match = _MD_QUAL_ALIAS.search(qual)
        # FK rows always carry an FK column on this object, so direct=True.
        return RelatedObject(
            name=alias_match.group(1) if alias_match else arrow.group("target"),
            cardinality=_normalize_card(qual),
            direct_relationship=True,
            path=_extract_via(qual),
        )

    plain = _MD_REL_PLAIN.match(text)
    if not plain:
        return None
    qual = plain.group("qual") or ""
    return RelatedObject(
        name=plain.group("name"),
        cardinality=_normalize_card(qual),
        direct_relationship=False,
        path=_extract_via(qual),
    )


def _normalize_card(qual: str) -> str | None:
    match = _MD_QUAL_CARD.search(qual)
    if not match:
        return None
    return match.group(1).upper().replace("-", "_")


def _extract_via(qual: str) -> str | None:
    match = _MD_QUAL_VIA.search(qual)
    return match.group(1) if match else None
