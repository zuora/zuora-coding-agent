"""Deterministic Callout body expansion when no LLM renderer is available."""

from __future__ import annotations

import json
import re
from typing import Any

_LIQUID_PATH = re.compile(
    r"^\{\{\s*(?:Data\.)?([A-Za-z][\w]*(?:\.[A-Za-z][\w]*)*)\s*\}\}$"
)
_NUMERIC_FIELD_SUFFIXES = (
    "Amount",
    "Balance",
    "Quantity",
    "Count",
    "Number",
    "Total",
    "Price",
    "Rate",
    "Percent",
    "Mrr",
    "Tcv",
    "Tax",
    "Qty",
)


def _normalize_liquid(expr: str) -> str:
    text = (expr or "").strip()
    if not text:
        return ""
    if text.startswith("{{") and text.endswith("}}"):
        return text
    if text.startswith("Data."):
        return f"{{{{{text}}}}}"
    return f"{{{{Data.{text}}}}}"


def _field_tail(path: str) -> str:
    return path.split(".")[-1] if path else "value"


def _json_key_from_path(path: str) -> str:
    tail = _field_tail(path)
    if not tail:
        return "value"
    if tail == "Id":
        return "id"
    if tail.endswith("Id") and len(tail) > 2:
        return tail[0].lower() + tail[1:-2] + "Id"
    return tail[0].lower() + tail[1:]


def _should_quote_liquid(liquid: str) -> bool:
    match = _LIQUID_PATH.match(liquid.strip())
    if not match:
        return True
    tail = _field_tail(match.group(1))
    if tail in {"Id", "Status", "Type", "Name", "Number", "Date", "Email"}:
        return True
    return not any(tail.endswith(suffix) for suffix in _NUMERIC_FIELD_SUFFIXES)


def _render_scalar(liquid: str) -> str:
    if _should_quote_liquid(liquid):
        return json.dumps(liquid)
    return liquid


def render_callout_body_from_brief(
    *,
    url: str,
    method: str,
    body_brief: str,
    body_vars: list[Any],
    workflow_name: str = "",
    task_name: str = "",
) -> str:
    """Expand ``body_brief`` + ``body_vars`` into a minimal Liquid JSON ``raw_body``.

  This is a deterministic fallback for coding-agent builds. It maps each
  ``body_vars`` entry to a snake/camelCase JSON key and applies basic quoting
  rules for string vs numeric Liquid paths.
    """
    _ = (url, method, body_brief, workflow_name, task_name)
    entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in body_vars or []:
        liquid = _normalize_liquid(str(raw))
        if not liquid:
            continue
        match = _LIQUID_PATH.match(liquid)
        path = match.group(1) if match else str(raw)
        key = _json_key_from_path(path)
        if key in seen:
            suffix = 2
            candidate = f"{key}{suffix}"
            while candidate in seen:
                suffix += 1
                candidate = f"{key}{suffix}"
            key = candidate
        seen.add(key)
        entries.append((key, liquid))

    if not entries:
        return "{}"

    inner = ",\n  ".join(f'"{key}": {_render_scalar(liquid)}' for key, liquid in entries)
    return "{\n  " + inner + "\n}"
