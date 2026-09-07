"""Strict validation for assembled Zuora Workflow export JSON (import payload).

Validation happens in three layers:

1. ``WorkflowExportStrict`` — top-level import-document shape
   (``workflow_definition`` + ``workflow`` + ``tasks`` + ``linkages``).
   Enforces ``extra="forbid"`` so any stray keys on known blocks are
   caught immediately.
2. ``ModelEnforcementEngine`` — in-place strips parameters that are not
   declared on the task's ``<Action>TaskParameters`` Pydantic model.
   Common pass-through keys (``strict_variables``, ``disable_validation``,
   ``delete_payload_paths``, creative brief keys, etc.) are preserved.
   This is purely defensive: ``TaskTemplateEngine`` already filters, but
   untrusted callers of ``validate_workflow_export_strict`` benefit from
   a second pass.
3. Per-task discriminated validation via ``TASK_TYPE_TASK_MAP`` — each
   task dict is run through its ``<Action>Task`` Pydantic model, which
   transitively enforces required top-level fields (``object`` /
   ``object_id``), required parameters, parameter types, regex patterns,
   ``Literal[...]`` enums, and any ``if/then/else`` cross-field rules
   declared in the upstream JSON schemas.

No reads of any JSON manifest — the generated Pydantic registry
(``TASK_TYPE_CONFIG_MAP``, ``TASK_TYPE_TASK_MAP``) is the sole source of
truth.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from workflow_engine.workflow_reference.models import (
    TASK_TYPE_CONFIG_MAP,
    TASK_TYPE_TASK_MAP,
)


class WorkflowDefinitionExport(BaseModel):
    """workflow_definition block."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1)
    description: str = ""
    category: str = "Default"
    ui_page_roles: list[Any] = Field(default_factory=list)


class WorkflowNotificationsExport(BaseModel):
    """Rails DB default for notifications is {} — all fields are optional."""

    model_config = ConfigDict(extra="forbid")

    emails: list[Any] = Field(default_factory=list)
    failure: Optional[bool] = None
    success: Optional[bool] = None
    pending: Optional[bool] = None
    skipped_scheduled_run: Optional[bool] = None
    error_ignore: Optional[str] = None


class WorkflowParametersExport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: list[Any] = Field(default_factory=list)
    skipping_check: Optional[str] = "none"
    event_triggers: list[str] = Field(default_factory=list)
    event_parameters: list[Any] = Field(default_factory=list)
    merge_task_ids: list[Any] = Field(default_factory=list)
    disable_pending_status: bool = False
    secure_error_msgs: Optional[str] = "false"
    legacy_boolean_input: bool = False
    callout_response: Optional[str] = "workflow instance"
    file_encryption: Any = None
    show_run_prompt: Any = None


class WorkflowBlockExport(BaseModel):
    """workflow block (Workflow::Setup)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1)
    description: str = ""
    status: str = Field(pattern=r"^(Active|Inactive)$")
    priority: str = Field(pattern=r"^(Low|Medium|High)$")
    call_type: Optional[str] = None
    version: str = Field(pattern=r"^\d+(?:\.\d+){0,2}$")
    ondemand_trigger: bool = False
    callout_trigger: bool = False
    scheduled_trigger: bool = False
    event_trigger: bool = False
    ui_trigger: bool = False
    interval: Optional[str] = None
    timezone: Optional[str] = None
    delete_ttl: int = Field(ge=0, default=30)
    data: dict[str, Any] = Field(default_factory=dict)
    notifications: WorkflowNotificationsExport = Field(default_factory=WorkflowNotificationsExport)
    parameters: WorkflowParametersExport = Field(default_factory=WorkflowParametersExport)
    css: dict[str, Any] = Field(default_factory=dict)
    type: Literal["Workflow::Setup"] = "Workflow::Setup"
    ui_pages: dict[str, Any] = Field(default_factory=dict)
    solution_id: Any = None
    extension_id: Any = None
    zuora_org_id: Any = None
    zuora_org_ids: list[Any] = Field(default_factory=list)


class ExportTaskModel(BaseModel):
    """Shape-level validation for a single task in the export.

    This is deliberately *lenient* on ``parameters`` (``dict[str, Any]``)
    because the strict, action-type-aware check runs separately via
    ``TASK_TYPE_TASK_MAP[action_type]`` inside
    ``validate_workflow_export_strict``.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: int
    name: str = Field(min_length=1)
    action_type: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    object: Optional[str] = None
    object_id: Optional[str] = None
    call_type: str = "SOAP"
    task_id: Optional[int] = None
    concurrent_limit: int = Field(ge=1, default=9999999)
    priority: str = Field(pattern=r"^(Low|Medium|High)$", default="Medium")
    tags: list[Any] = Field(default_factory=list)
    assignment: list[Any] = Field(default_factory=list)
    entity_id: Any = None
    zuora_org_id: Any = None
    zuora_org_ids: list[Any] = Field(default_factory=list)
    subprocess_id: Optional[int] = None
    css: dict[str, Any] = Field(default_factory=dict)


class LinkageExport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_workflow_id: Optional[int] = None
    source_task_id: Optional[int] = None
    target_task_id: int
    linkage_type: str = Field(min_length=1)


class WorkflowExportStrict(BaseModel):
    """Full import document: workflow_definition + workflow + tasks + linkages."""

    model_config = ConfigDict(extra="forbid")

    workflow_definition: WorkflowDefinitionExport
    workflow: WorkflowBlockExport
    tasks: list[ExportTaskModel] = Field(min_length=1)
    linkages: list[LinkageExport] = Field(min_length=1)


class ModelEnforcementEngine:
    """Strip parameters not defined on ``<Action>TaskParameters``.

    Mirrors the old assembly-time enforcement, but now reads the allowed
    set straight from ``TASK_TYPE_CONFIG_MAP[action].model_fields``.

    Common pass-through keys (Rails accepts them on most task types but
    they are modeled on ``CommonTaskParameters``) are always kept, as are
    creative-brief stand-ins (``intent``, ``body_brief``, ``tone``, etc.)
    that the creative sub-agent may embed on a draft task.
    """

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
    _CALLOUT_EXTRA: frozenset[str] = frozenset(
        {
            "files",
            "form_datas",
            "api_name",
            "api_doc_url",
            "notification_history_enabled",
        }
    )

    def __init__(self) -> None:
        self._cache: dict[str, Optional[set[str]]] = {}

    def _allowed(self, action_type: str) -> Optional[set[str]]:
        if action_type in self._cache:
            return self._cache[action_type]
        config_class = TASK_TYPE_CONFIG_MAP.get(action_type)
        if config_class is None:
            self._cache[action_type] = None
            return None
        allowed = set(getattr(config_class, "model_fields", {}).keys())
        self._cache[action_type] = allowed
        return allowed

    def enforce(self, task: dict) -> list[str]:
        """Strip unknown parameters in-place; return list of removed keys (informational)."""
        action_type = task.get("action_type", "")
        allowed = self._allowed(action_type)
        if allowed is None:
            return []
        params = task.get("parameters")
        if not params:
            return []
        keep = allowed | self._COMMON_PASS_THROUGH
        if action_type in ("Callout", "AsynchronousCallout"):
            keep = keep | self._CALLOUT_EXTRA
        removed = [k for k in params if k not in keep]
        for k in removed:
            del params[k]
        return removed


def _validate_task_strict(task: dict[str, Any]) -> list[str]:
    """Validate a single task dict against its ``<Action>Task`` Pydantic model.

    Returns a list of human-readable error strings; empty list = pass.
    """
    action_type = task.get("action_type", "")
    task_cls = TASK_TYPE_TASK_MAP.get(action_type)
    if task_cls is None:
        return [f"Unknown action_type: {action_type!r}"]
    try:
        task_cls.model_validate(task)
    except ValidationError as e:
        return [_format_pydantic_error(err) for err in e.errors()]  # type: ignore[arg-type]
    return []


def _format_pydantic_error(err: dict[str, Any]) -> str:
    loc = ".".join(str(p) for p in err.get("loc", []))
    msg = err.get("msg", "validation error")
    return f"{loc}: {msg}" if loc else msg


def validate_workflow_export_strict(
    data: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Run Pydantic strict model validation on the full export payload.

    Layers:
        1. ``WorkflowExportStrict`` — overall document shape.
        2. ``ModelEnforcementEngine`` — scrub unknown parameter keys in place.
        3. ``<Action>Task`` Pydantic validation — full strict checks per task.

    Returns ``(ok, list of error strings)``.
    """
    errors: list[str] = []
    try:
        export = WorkflowExportStrict.model_validate(data)
    except ValidationError as e:
        return False, [f"Pydantic export validation: {e}"]
    except Exception as e:
        return False, [f"Pydantic export validation: {e}"]

    enforcer = ModelEnforcementEngine()
    tasks_raw = data.get("tasks", [])
    for raw_task in tasks_raw:
        enforcer.enforce(raw_task)

    for t in export.tasks:
        task_dict = t.model_dump()
        task_errors = _validate_task_strict(task_dict)
        for msg in task_errors:
            errors.append(f"Task {t.id} ({t.name}): {msg}")

    return (len(errors) == 0, errors)
