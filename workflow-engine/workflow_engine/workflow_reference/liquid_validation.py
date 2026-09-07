"""Liquid syntax validation for workflow expressions.

Validates Liquid templating syntax before assembly to catch common errors early.
Ported from old agent validation/liquid.py with full parity.
"""

from __future__ import annotations

import re


class LiquidValidationError(Exception):
    """Raised when Liquid syntax validation fails."""


def validate_liquid_syntax(code: str) -> list[str]:
    """Validate basic Liquid syntax.

    Checks for balanced tags, common assign errors, unclosed blocks.
    Returns list of error messages (empty if valid).
    """
    errors: list[str] = []

    if not code:
        return errors

    opens = len(re.findall(r"\{%", code))
    closes = len(re.findall(r"%\}", code))
    if opens != closes:
        errors.append(f"Unbalanced Liquid tags: {opens} opens, {closes} closes")

    opens = len(re.findall(r"\{\{", code))
    closes = len(re.findall(r"\}\}", code))
    if opens != closes:
        errors.append(f"Unbalanced output tags: {opens} opens, {closes} closes")

    # [*] notation is invalid inside Iterate For Each path
    if re.search(r"\{\{\s*Data\.[^}]+\[\*\]\.[^}]+\s*\}\}", code):
        errors.append(
            "Inside Iterate For Each, use Data.<ObjectName>.Field where "
            "<ObjectName> matches the Iterate task's object field "
            "(not Data.X[*].Field)"
        )

    for match in re.findall(r"\{%\s*assign\s+([^%]+)%\}", code):
        if "=" not in match:
            errors.append(
                f"Invalid assign syntax: missing '=' in " f"'{{% assign {match.strip()} %}}'"
            )

    for_opens = len(re.findall(r"\{%\s*for\s", code))
    for_closes = len(re.findall(r"\{%\s*endfor\s*%\}", code))
    if for_opens != for_closes:
        errors.append(f"Unbalanced for loops: {for_opens} opens, {for_closes} closes")

    if_opens = len(re.findall(r"\{%\s*if\s", code))
    if_closes = len(re.findall(r"\{%\s*endif\s*%\}", code))
    if if_opens != if_closes:
        errors.append(f"Unbalanced if statements: {if_opens} opens, {if_closes} closes")

    capture_opens = len(re.findall(r"\{%\s*capture\s", code))
    capture_closes = len(re.findall(r"\{%\s*endcapture\s*%\}", code))
    if capture_opens != capture_closes:
        errors.append(f"Unbalanced capture blocks: {capture_opens} opens, {capture_closes} closes")

    return errors


_DATA_LIQUID_PROPERTY = re.compile(r"Data\.Liquid\.[A-Za-z_][A-Za-z0-9_]*")


def validate_logic_liquid_data_liquid_reads(code: str, available_before: set[str]) -> list[str]:
    """Warn when ``Logic::Liquid`` code reads ``Data.Liquid.<key>`` not present before this task.

    ``Data.Liquid.*`` is populated after a ``Logic::Liquid`` task completes (and keyed by
    prior ``{% assign name = ... %}`` outputs). Reading ``Data.Liquid.log_entries`` inside
    the same task that assigns ``log_entries`` is invalid at runtime.
    """
    warnings: list[str] = []
    if not code:
        return warnings

    seen: set[str] = set()
    for match in _DATA_LIQUID_PROPERTY.finditer(code):
        full_path = match.group(0)
        if full_path in seen:
            continue
        seen.add(full_path)
        if full_path not in available_before:
            warnings.append(
                f"Reference '{full_path}' is not available before this Logic::Liquid task runs — "
                "do not read Data.Liquid.* inside the same task's code; only later tasks may use "
                "{{ Data.Liquid.<name> }}. For single-task shaping use plain "
                "{% assign <name> = ... %} without reading Data.Liquid.<name> mid-template."
            )

    return warnings


def mask_data_liquid_property_reads(code: str) -> str:
    """Replace ``Data.Liquid.<id>`` so :func:`validate_liquid_references` does not treat
    them as the ``Data.Liquid`` root only (first path segment).
    """
    if not code:
        return code
    return _DATA_LIQUID_PROPERTY.sub("Data.Workflow", code)


def validate_liquid_references(code: str, available_data: set[str]) -> list[str]:
    """Validate that referenced data paths are available.

    Returns list of warning messages for potentially unavailable references.
    """
    warnings: list[str] = []

    if not code:
        return warnings

    refs = re.findall(r"Data\.(\w+)", code)

    for ref in refs:
        full_ref = f"Data.{ref}"

        if ref in ("Object", "Workflow", "UIAction", "Files", "Callout", "LinkData"):
            continue

        if full_ref not in available_data:
            if not any(avail.startswith(full_ref) for avail in available_data):
                warnings.append(f"Reference '{full_ref}' may not be available")

    return warnings


def validate_email_template(template: str) -> list[str]:
    """Validate an email HTML template (Liquid syntax within it)."""
    errors: list[str] = []

    if not template:
        errors.append("Email template is empty")
        return errors

    errors.extend(validate_liquid_syntax(template))
    return errors


def validate_callout_body(body: str) -> list[str]:
    """Validate a Callout task body for Liquid syntax issues."""
    if not body:
        return []
    return validate_liquid_syntax(body)


def extract_data_references(code: str) -> list[str]:
    """Extract all unique Data.X references from Liquid code."""
    if not code:
        return []

    refs = re.findall(r"Data\.[\w.]+", code)

    seen: set[str] = set()
    unique: list[str] = []
    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            unique.append(ref)
    return unique
