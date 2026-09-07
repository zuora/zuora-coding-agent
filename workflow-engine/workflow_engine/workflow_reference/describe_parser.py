"""XML parser for the Zuora ``/v1/describe`` catalog + per-object endpoints.

Two endpoints are covered:

* ``GET /v1/describe``
    Returns the object catalog - one ``<object>`` entry per object with
    ``name``/``label``/``href``.  See :func:`parse_object_catalog`.

* ``GET /v1/describe/{object}?showRelationships=true``
    Returns one ``<object>`` with ``<fields>`` and ``<related-objects>``.
    See :func:`parse_object_describe`.

The parser is deliberately tolerant: missing children decay to sane defaults
and empty strings are coerced to ``None``.  Boolean flags (``selectable``,
``createable`` etc.) are returned as real booleans.  Picklist
``<options>`` and per-field ``<contexts>`` are returned as lists.

All parsing uses the stdlib ``xml.etree.ElementTree`` and is safe against
regular Zuora responses; no DTD/entity resolution is attempted.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Iterable

import defusedxml.ElementTree as _safe_ET  # noqa: N812

__all__ = [
    "CatalogEntry",
    "FieldInfo",
    "RelatedObject",
    "ObjectDescribe",
    "parse_object_catalog",
    "parse_object_describe",
    "infer_foreign_key_field",
    "DescribeParseError",
]


class DescribeParseError(ValueError):
    """Raised when a describe payload cannot be parsed into a known shape."""


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CatalogEntry:
    """One row from ``GET /v1/describe``."""

    name: str
    label: str | None = None
    href: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "label": self.label, "href": self.href}


@dataclass(frozen=True)
class FieldInfo:
    """Per-field metadata inside an :class:`ObjectDescribe`."""

    name: str
    label: str | None = None
    type: str | None = None
    selectable: bool = False
    createable: bool = False
    updateable: bool = False
    filterable: bool = False
    custom: bool = False
    required: bool = False
    maxlength: int | None = None
    options: tuple[str, ...] = ()
    contexts: tuple[str, ...] = ()

    def is_queryable(self) -> bool:
        """True when the field is allowed in Query tasks (ZOQL via SOAP)."""
        return self.selectable and ("soap" in self.contexts or not self.contexts)

    def is_exportable(self) -> bool:
        """True when the field is allowed in an Export task (AQuA/ZOQL export)."""
        return self.selectable and "export" in self.contexts

    def is_updatable(self) -> bool:
        """True when the field may be written in Update tasks."""
        return self.updateable

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "type": self.type,
            "selectable": self.selectable,
            "createable": self.createable,
            "updateable": self.updateable,
            "filterable": self.filterable,
            "custom": self.custom,
            "required": self.required,
            "maxlength": self.maxlength,
            "options": list(self.options),
            "contexts": list(self.contexts),
        }


@dataclass(frozen=True)
class RelatedObject:
    """One ``<related-objects>/<object>`` entry."""

    name: str
    label: str | None = None
    cardinality: str | None = None
    direct_relationship: bool = False
    path: str | None = None
    href: str | None = None

    @property
    def is_to_one(self) -> bool:
        return (self.cardinality or "").upper() in {"TO_ONE", "ONE_TO_ONE", "MANY_TO_ONE"}

    @property
    def is_to_many(self) -> bool:
        return (self.cardinality or "").upper() in {"TO_MANY", "ONE_TO_MANY", "MANY_TO_MANY"}

    def foreign_key_on(self, parent: "ObjectDescribe | None") -> str | None:
        """Return the FK column on ``parent`` that connects to this relation.

        Only meaningful for TO_ONE relationships — a TO_MANY child holds its
        own back-reference FK, not the parent. Returns ``None`` when
        ``parent`` is ``None``, when the relation is not TO_ONE, or when no
        matching ``<alias>Id`` / ``<alias>ID`` field exists on the parent.
        """
        if parent is None or not self.is_to_one:
            return None
        return infer_foreign_key_field(parent, self.name)

    def to_dict(self, parent: "ObjectDescribe | None" = None) -> dict[str, Any]:
        """Serialize this relation.

        When ``parent`` is provided, include ``foreign_key_field`` — the column
        on the parent that carries the FK (e.g. ``Invoice.AccountId`` for
        ``Invoice -> Account``). The key is always present for a stable
        contract; it is ``None`` when no FK column can be inferred (indirect
        navigation, TO_MANY children, parent unavailable).
        """
        return {
            "name": self.name,
            "label": self.label,
            "cardinality": self.cardinality,
            "direct_relationship": self.direct_relationship,
            "path": self.path,
            "href": self.href,
            "foreign_key_field": self.foreign_key_on(parent),
        }


@dataclass(frozen=True)
class ObjectDescribe:
    """Full ``GET /v1/describe/{object}`` payload."""

    name: str
    label: str | None = None
    href: str | None = None
    fields: tuple[FieldInfo, ...] = field(default_factory=tuple)
    related_objects: tuple[RelatedObject, ...] = field(default_factory=tuple)

    # ------------------------------------------------------------------
    # Convenience lookups (used by resolver / plan_validator callers)
    # ------------------------------------------------------------------

    def field_by_name(self, name: str) -> FieldInfo | None:
        lowered = name.lower()
        for f in self.fields:
            if f.name.lower() == lowered:
                return f
        return None

    def selectable_field_names(self) -> list[str]:
        return [f.name for f in self.fields if f.selectable]

    def exportable_field_names(self) -> list[str]:
        return [f.name for f in self.fields if f.is_exportable()]

    def queryable_field_names(self) -> list[str]:
        return [f.name for f in self.fields if f.is_queryable()]

    def updatable_field_names(self) -> list[str]:
        return [f.name for f in self.fields if f.updateable]

    def filterable_field_names(self) -> list[str]:
        return [f.name for f in self.fields if f.filterable]

    def to_one_relationships(self) -> list[RelatedObject]:
        return [r for r in self.related_objects if r.is_to_one]

    def to_many_relationships(self) -> list[RelatedObject]:
        return [r for r in self.related_objects if r.is_to_many]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "href": self.href,
            "fields": [f.to_dict() for f in self.fields],
            "related_objects": [r.to_dict(parent=self) for r in self.related_objects],
        }


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------


def _text(el: ET.Element | None, tag: str, default: str | None = None) -> str | None:
    if el is None:
        return default
    child = el.find(tag)
    if child is None or child.text is None:
        return default
    value = child.text.strip()
    return value or default


def _bool(el: ET.Element | None, tag: str) -> bool:
    raw = (_text(el, tag) or "").strip().lower()
    return raw in {"true", "1", "yes"}


def _int(el: ET.Element | None, tag: str) -> int | None:
    raw = _text(el, tag)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _strip_all_text(values: Iterable[str | None]) -> tuple[str, ...]:
    out: list[str] = []
    for v in values:
        if v is None:
            continue
        stripped = v.strip()
        if stripped:
            out.append(stripped)
    return tuple(out)


def _parse_xml(payload: str | bytes | ET.Element) -> ET.Element:
    if isinstance(payload, ET.Element):
        return payload
    try:
        if isinstance(payload, bytes):
            return _safe_ET.fromstring(payload)
        return _safe_ET.fromstring(payload)
    except ET.ParseError as exc:  # pragma: no cover - defensive
        raise DescribeParseError(f"Invalid describe XML: {exc}") from exc


# ---------------------------------------------------------------------------
# Public parsers
# ---------------------------------------------------------------------------


def parse_object_catalog(payload: str | bytes | ET.Element) -> list[CatalogEntry]:
    """Parse ``GET /v1/describe`` into a list of :class:`CatalogEntry`.

    Accepts either a raw XML string/bytes payload or a parsed root element.
    Missing labels/hrefs decay to ``None`` and entries without a name are
    silently skipped.
    """
    root = _parse_xml(payload)

    if root.tag != "objects":
        found = root.find("objects")
        if found is None:
            raise DescribeParseError(
                f"Expected <objects> root, got <{root.tag}>",
            )
        root = found

    entries: list[CatalogEntry] = []
    for obj in root.findall("object"):
        name = _text(obj, "name")
        if not name:
            continue
        entries.append(
            CatalogEntry(
                name=name,
                label=_text(obj, "label"),
                href=obj.get("href") or _text(obj, "href"),
            ),
        )
    return entries


def _parse_field(el: ET.Element) -> FieldInfo | None:
    name = _text(el, "name")
    if not name:
        return None

    options_el = el.find("options")
    options: tuple[str, ...] = ()
    if options_el is not None:
        options = _strip_all_text(opt.text for opt in options_el.findall("option"))

    contexts_el = el.find("contexts")
    contexts: tuple[str, ...] = ()
    if contexts_el is not None:
        contexts = _strip_all_text(ctx.text for ctx in contexts_el.findall("context"))

    return FieldInfo(
        name=name,
        label=_text(el, "label"),
        type=_text(el, "type"),
        selectable=_bool(el, "selectable"),
        createable=_bool(el, "createable"),
        updateable=_bool(el, "updateable"),
        filterable=_bool(el, "filterable"),
        custom=_bool(el, "custom"),
        required=_bool(el, "required"),
        maxlength=_int(el, "maxlength"),
        options=options,
        contexts=contexts,
    )


def _parse_related_object(el: ET.Element) -> RelatedObject | None:
    name = _text(el, "name")
    if not name:
        return None
    return RelatedObject(
        name=name,
        label=_text(el, "label"),
        cardinality=_text(el, "cardinality"),
        direct_relationship=_bool(el, "direct-relationship"),
        path=_text(el, "path"),
        href=el.get("href") or _text(el, "href"),
    )


# ---------------------------------------------------------------------------
# Foreign-key inference
# ---------------------------------------------------------------------------


def infer_foreign_key_field(parent: ObjectDescribe, alias: str) -> str | None:
    """Return the FK column on ``parent`` that targets ``alias``, or ``None``.

    Zuora consistently names FK columns as ``<Alias>Id`` (or the legacy
    ``<Alias>ID``). For example, the ``Account`` relation on ``Invoice`` is
    connected by ``Invoice.AccountId``; the ``BillToContact`` relation on
    ``Invoice`` is connected by ``Invoice.BillToContactId``. If neither
    candidate column is present on ``parent``, the relation is indirect
    (navigation-only) and this returns ``None``.

    Returns the field's real, exactly-cased name (not the candidate we built)
    so consumers emit an FK string that matches the schema verbatim.

    This is the single source of truth for FK inference across the codebase;
    build_docs (markdown writer), describe_parser (JSON writer), and
    object_metadata (graph builder) all consume it.
    """
    for candidate in (f"{alias}Id", f"{alias}ID"):
        found = parent.field_by_name(candidate)
        if found is not None:
            return found.name
    return None


def parse_object_describe(payload: str | bytes | ET.Element) -> ObjectDescribe:
    """Parse ``GET /v1/describe/{object}?showRelationships=true``.

    Returns an :class:`ObjectDescribe` with fields and related-objects.
    """
    root = _parse_xml(payload)

    if root.tag != "object":
        found = root.find("object")
        if found is None:
            raise DescribeParseError(
                f"Expected <object> root, got <{root.tag}>",
            )
        root = found

    name = _text(root, "name")
    if not name:
        raise DescribeParseError("Describe response missing <name>")

    fields_el = root.find("fields")
    fields: tuple[FieldInfo, ...] = ()
    if fields_el is not None:
        parsed_fields = [_parse_field(f) for f in fields_el.findall("field")]
        fields = tuple(f for f in parsed_fields if f is not None)

    related_el = root.find("related-objects")
    related: tuple[RelatedObject, ...] = ()
    if related_el is not None:
        parsed_rel = [_parse_related_object(r) for r in related_el.findall("object")]
        related = tuple(r for r in parsed_rel if r is not None)

    return ObjectDescribe(
        name=name,
        label=_text(root, "label"),
        href=root.get("href") or _text(root, "href"),
        fields=fields,
        related_objects=related,
    )
