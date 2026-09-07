"""Markdown formatter for lookup_workflow_reference CLI."""

from __future__ import annotations

from typing import Optional

from workflow_engine.workflow_reference.reference_lookup import lookup


def lookup_workflow_reference(topic: str, subtopic: Optional[str] = None) -> str:
    result = lookup(topic, subtopic)
    return result.get("content", "(no content)")
