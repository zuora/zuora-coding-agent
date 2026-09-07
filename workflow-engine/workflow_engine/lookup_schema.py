"""CLI-oriented lookup_zuora_schema (no Strands runtime)."""

from __future__ import annotations

import asyncio
from typing import Optional

from workflow_engine.workflow_reference.describe_parser import FieldInfo, ObjectDescribe, RelatedObject
from workflow_engine.workflow_reference.object_metadata import ObjectMetadataResult, get_object_metadata
from workflow_engine.zuora_http import session_from_env


def _format_field_line(f: FieldInfo) -> str:
    flag_bits: list[str] = []
    if f.selectable:
        flag_bits.append("selectable")
    if f.createable:
        flag_bits.append("createable")
    if f.updateable:
        flag_bits.append("updateable")
    if f.filterable:
        flag_bits.append("filterable")
    if f.required:
        flag_bits.append("required")
    if f.custom:
        flag_bits.append("custom")

    type_bit = f" [{f.type}]" if f.type else ""
    flags_bit = f" ({', '.join(flag_bits)})" if flag_bits else ""
    ctx_bit = f" ctx=[{', '.join(f.contexts)}]" if f.contexts else ""
    if f.options and len(f.options) <= 12:
        opts_bit = f" options=[{', '.join(f.options)}]"
    elif f.options:
        opts_bit = f" options=[{len(f.options)} values]"
    else:
        opts_bit = ""
    return f"- {f.name}{type_bit}{flags_bit}{ctx_bit}{opts_bit}"


def _format_relationship_line(rel: RelatedObject, parent: ObjectDescribe | None = None) -> str:
    direct = "direct" if rel.direct_relationship else "indirect"
    cardinality = rel.cardinality or "UNKNOWN"
    path = f" path={rel.path}" if rel.path else ""
    fk_suffix = ""
    fk_field = rel.foreign_key_on(parent) if parent is not None else None
    if fk_field is not None and parent is not None:
        fk_suffix = f" fk={parent.name}.{fk_field}"
    return f"- {rel.name} ({cardinality}, {direct}){path}{fk_suffix}"


def format_describe(
    result: ObjectMetadataResult,
    *,
    include_fields: bool = True,
    include_custom_fields: bool = True,
    include_relationships: bool = False,
    context_filter: Optional[str] = None,
) -> str:
    describe = result.describe
    if describe is None:
        return f"Object not found ({result.error or 'no source available'})"

    lines: list[str] = [f"## {describe.name} Schema"]
    if describe.label:
        lines.append(f"Label: {describe.label}")
    lines.append(f"Source: {result.source}")
    if not result.is_authoritative:
        lines.append(
            "_Schema came from a degraded source; per-field flags and "
            "contexts may be missing. Set ZUORA_* env vars for live /describe._"
        )

    if include_fields:
        fields = list(describe.fields)
        if context_filter:
            lowered = context_filter.lower()
            fields = [f for f in fields if lowered in {c.lower() for c in f.contexts}]
        if not include_custom_fields:
            fields = [f for f in fields if not f.custom]

        if fields:
            header_suffix = f" (context={context_filter})" if context_filter else ""
            lines.append("")
            lines.append(f"### Fields ({len(fields)}){header_suffix}")
            for f in fields:
                lines.append(_format_field_line(f))
        elif context_filter:
            lines.append("")
            lines.append(f"### Fields\n_No fields available for context {context_filter!r}._")

    if include_relationships and describe.related_objects:
        lines.append("")
        lines.append(f"### Related Objects ({len(describe.related_objects)})")
        for rel in describe.related_objects:
            lines.append(_format_relationship_line(rel, describe))

    return "\n".join(lines)


async def lookup_zuora_schema_async(
    object_name: str,
    *,
    include_fields: bool = True,
    include_custom_fields: bool = True,
    include_relationships: bool = False,
    context_filter: Optional[str] = None,
) -> str:
    if not object_name or not object_name.strip():
        return "Error: `object_name` is required."

    session = session_from_env()
    result = await get_object_metadata(object_name.strip(), session)
    if result.describe is None:
        return (
            f"Object {object_name!r} not found. Verify spelling (case-sensitive). "
            f"({result.error or 'no source available'})"
        )
    return format_describe(
        result,
        include_fields=include_fields,
        include_custom_fields=include_custom_fields,
        include_relationships=include_relationships,
        context_filter=context_filter,
    )


def lookup_zuora_schema(
    object_name: str,
    *,
    include_fields: bool = True,
    include_custom_fields: bool = True,
    include_relationships: bool = False,
    context_filter: Optional[str] = None,
) -> str:
    return asyncio.run(
        lookup_zuora_schema_async(
            object_name,
            include_fields=include_fields,
            include_custom_fields=include_custom_fields,
            include_relationships=include_relationships,
            context_filter=context_filter,
        )
    )
