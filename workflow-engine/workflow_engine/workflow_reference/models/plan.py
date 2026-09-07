"""Hand-authored LLM-output types (workflow plan, intent, logical plan).

These models describe the shape the agent/LLM produces; they are *not*
generated from the manifest. Task-specific parameter validation delegates to
``TASK_TYPE_CONFIG_MAP`` from ``task_registry`` (which points to the
Pydantic classes generated from JSON schemas in ``generated.py``).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .task_registry import TASK_TYPE_CONFIG_MAP, TaskTypeEnum

# ---------------------------------------------------------------------------
# Compatibility shim — generate_workflow.py calls set_valid_task_types() after
# loading the task catalog. With TaskTypeEnum this is now a no-op, but the
# symbol is kept so existing imports don't break.
# ---------------------------------------------------------------------------
_VALID_TASK_TYPES: set[str] = set()


def set_valid_task_types(task_types: set[str]) -> None:
    """No-op compatibility shim — validation now uses ``TaskTypeEnum``."""
    global _VALID_TASK_TYPES
    _VALID_TASK_TYPES = task_types


# ---------------------------------------------------------------------------
# Trigger / Plan models
# ---------------------------------------------------------------------------


class TriggerConfig(BaseModel):
    """Workflow trigger configuration."""

    type: Literal["ondemand", "scheduled", "event", "callout"]
    scheduled_interval: str | None = None
    scheduled_timezone: str | None = None
    event_names: list[str] = Field(default_factory=list)
    event_parameters: list[dict] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_scheduled_fields(self) -> "TriggerConfig":
        if self.type == "scheduled":
            if not self.scheduled_interval:
                raise ValueError("scheduled_interval required for scheduled trigger")
            if not self.scheduled_timezone:
                raise ValueError("scheduled_timezone required for scheduled trigger")
        if self.type == "event" and not self.event_names:
            raise ValueError("event_names required for event trigger")
        return self


class InputField(BaseModel):
    """A single workflow input parameter (shown in the workflow's Parameters tab)."""

    field_name: str
    object_name: str
    datatype: Literal["String", "Boolean", "Integer", "Decimal", "Date", "DateTime", "JSON"]
    required: bool = False
    default: str = ""
    callout_id: str = ""


# Parameter names that are common pass-throughs and not subject to per-task
# schema validation. Duplicated from TaskTemplateEngine so ``PlanTask``
# doesn't import it (and thus avoid a circular dependency).
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

# Placeholders that let pydantic accept values that will be resolved by the
# assembler downstream (e.g. Iterate.object may be ``__auto_resolved__``).
_AUTO_RESOLVED_DEFAULTS: dict[str, dict[str, str]] = {
    "Iterate": {"object": "__auto_resolved__"},
}


class PlanTask(BaseModel):
    """A single task in the WorkflowPlan (action_type validated against TaskTypeEnum)."""

    id: int
    name: str
    action_type: str
    object: str | None = None
    object_id: str | None = None
    parameters: dict = Field(default_factory=dict)
    purpose: str = ""
    data_available_after: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_action_type_known(self) -> "PlanTask":
        valid = {e.value for e in TaskTypeEnum}
        if valid and self.action_type not in valid:
            sample = sorted(valid)[:10]
            raise ValueError(
                f"Unknown action_type '{self.action_type}'. "
                f"Valid types include: {sample}... (see get_task_catalog for the full list)"
            )
        return self

    @model_validator(mode="after")
    def validate_parameters_against_config(self) -> "PlanTask":
        """Plan-time check: reject unknown parameter names early.

        Full type-level validation (required fields, enum values, nested
        shapes, cross-field ``if/then/else`` rules) runs at *export* time via
        ``TaskUnion.model_validate`` in ``validate_workflow_export_strict``.
        Plans are drafts: briefs may stand in for ``template`` / ``raw_body``,
        and the creative sub-agent fills final values at build time.
        """
        config_class = TASK_TYPE_CONFIG_MAP.get(self.action_type)
        if config_class is None:
            return self
        allowed = set(getattr(config_class, "model_fields", {}).keys())
        if not allowed:
            return self
        unknown = set(self.parameters.keys()) - allowed - _COMMON_PASS_THROUGH
        if unknown:
            raise ValueError(
                f"Task '{self.name}' ({self.action_type}): unknown parameters "
                f"{sorted(unknown)}. Allowed: {sorted(allowed)}"
            )
        return self


class PlanLinkage(BaseModel):
    """A directed connection between two tasks (or from workflow_start to the first task)."""

    model_config = {"populate_by_name": True}

    from_: Any = Field(alias="from")
    to: int | None = None
    type: str

    @classmethod
    def model_validate(cls, obj: Any, **kwargs: Any) -> "PlanLinkage":
        if isinstance(obj, dict) and "from" in obj and "from_" not in obj:
            obj = dict(obj)
        return super().model_validate(obj, **kwargs)


class WorkflowTypeEnum(str, Enum):
    """Valid workflow types."""

    BATCH = "BATCH"
    REALTIME = "REALTIME"
    UIACTION = "UIACTION"


class WorkflowPlan(BaseModel):
    """Complete, validated workflow plan produced by analyze_requirements."""

    model_config = {"populate_by_name": True}

    name: str
    description: str
    call_type: Literal["ASYNC", "SYNC", "UI", "UIACTION", "BATCH", "REALTIME", "BUSINESS_PROCESS"]
    priority: Literal["Low", "Medium", "High"] = "Medium"
    trigger: TriggerConfig
    input_fields: list[InputField] = Field(default_factory=list)
    notifications: dict = Field(default_factory=dict)
    delete_ttl: int = 30
    tasks: list[PlanTask]
    linkages: list[PlanLinkage]
    data_payload_trace: list[dict] = Field(default_factory=list)
    meta: dict[str, Any] | None = Field(
        default=None,
        alias="_meta",
        description=(
            "LLM round-trip metadata. Carries intent, confidence, corrections, and "
            "assumptions (list of {field, value, reason, confidence}). Ignored by the "
            "assembler; used by the LLM to disclose auto-filled values to the user."
        ),
    )

    @model_validator(mode="after")
    def validate_linkage_task_ids_exist(self) -> "WorkflowPlan":
        task_ids = {t.id for t in self.tasks}
        for lnk in self.linkages:
            if lnk.to is not None and lnk.to not in task_ids:
                raise ValueError(
                    f"Linkage target task id {lnk.to} not found in tasks list. "
                    f"Existing task ids: {sorted(task_ids)}"
                )
            if isinstance(lnk.from_, int) and lnk.from_ not in task_ids:
                raise ValueError(
                    f"Linkage source task id {lnk.from_} not found in tasks list. "
                    f"Existing task ids: {sorted(task_ids)}"
                )
        return self

    @model_validator(mode="after")
    def validate_start_linkage_exists(self) -> "WorkflowPlan":
        entry = [
            lnk
            for lnk in self.linkages
            if str(lnk.from_) == "workflow_start" and lnk.to is not None
        ]
        if len(entry) != 1:
            raise ValueError(
                "Workflow must have exactly one linkage from workflow_start to the first task."
            )
        etype = entry[0].type
        if self.trigger.type == "event":
            names = self.trigger.event_names or []
            if etype not in ("Start",) and names and etype not in names:
                raise ValueError(
                    f"Event workflow entry linkage type must be 'Start' (normalized at build) "
                    f"or one of event_names {names}; got '{etype}'."
                )
        else:
            if etype != "Start":
                raise ValueError(
                    'Non-event workflows must use {"from": "workflow_start", "to": <id>, '
                    '"type": "Start"} for the entry linkage.'
                )
        return self


# ---------------------------------------------------------------------------
# TaskDecision / logical workflow plan (step_id-based structured planner)
# ---------------------------------------------------------------------------


def _validate_config_matches_type(data: dict) -> dict:
    if not isinstance(data, dict):
        return data
    task_type = data.get("task_type")
    config = data.get("config")
    if task_type is None or config is None:
        return data
    task_type_str = task_type.value if hasattr(task_type, "value") else str(task_type)
    expected_config_class = TASK_TYPE_CONFIG_MAP.get(task_type_str)
    if expected_config_class is None:
        return data
    if isinstance(config, dict):
        try:
            data["config"] = expected_config_class.model_validate(config)
        except Exception as e:
            raise ValueError(f"Config for task type '{task_type_str}' is invalid: {e}")
    return data


class TaskDecision(BaseModel):
    """A decision about what task to create."""

    sequence: int = Field(description="Order in workflow (1, 2, 3...)")
    task_type: TaskTypeEnum = Field(description="Type of task to create")
    name: str = Field(description="Human-readable task name")
    purpose: str = Field(description="What this task accomplishes")
    config: dict | BaseModel = Field(description="Task-specific configuration")
    success_target: int | None = Field(default=None, description="Sequence number on success")
    failure_target: int | None = Field(default=None, description="Sequence number on failure")
    branch_targets: dict[str, int] | None = Field(
        default=None, description="Branch name to sequence mapping"
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_config(cls, data: dict) -> dict:
        return _validate_config_matches_type(data)


def get_valid_branches(task_type: TaskTypeEnum) -> list[str] | None:
    """Get valid branch names for a task type."""
    branch_map = {
        TaskTypeEnum.IF: ["True", "False"],
        TaskTypeEnum.ITERATE: ["For Each", "Complete"],
        TaskTypeEnum.APPROVAL: ["Approve", "Reject", "Timeout"],
        TaskTypeEnum.LOGIC_CASE: ["Case_1", "Case_2", "Case_3", "..."],
    }
    return branch_map.get(task_type)


class LogicalStep(BaseModel):
    """A workflow step identified by a stable string id."""

    step_id: str = Field(description="Stable identifier for this step")
    task_type: TaskTypeEnum = Field(description="Type of task to create")
    name: str = Field(description="Human-readable task name")
    purpose: str = Field(description="What this task accomplishes")
    config: dict | BaseModel = Field(description="Task-specific configuration")

    @model_validator(mode="before")
    @classmethod
    def _coerce_config(cls, data: dict) -> dict:
        return _validate_config_matches_type(data)


class LogicalEdge(BaseModel):
    """Directed edge between steps by step_id."""

    from_step: str = Field(description="step_id of the source step")
    to_step: str = Field(description="step_id of the target step")
    edge_type: str = Field(
        description="Linkage type: Success, Failure, For Each, True, False, etc."
    )


class LogicalWorkflowPlan(BaseModel):
    """Logical workflow plan: steps with step_id and edges by name."""

    name: str = Field(description="Workflow name")
    description: str = Field(description="Workflow description")
    workflow_type: WorkflowTypeEnum = Field(
        default=WorkflowTypeEnum.BATCH, description="BATCH, REALTIME, or UIACTION"
    )
    trigger: TriggerConfig = Field(description="Trigger configuration")
    steps: list[LogicalStep] = Field(description="Steps with stable step_id")
    edges: list[LogicalEdge] = Field(description="Edges connecting steps by step_id")
    category: str = Field(default="Default", description="Workflow category/folder")

    @model_validator(mode="after")
    def validate_edges_refer_to_steps(self) -> "LogicalWorkflowPlan":
        step_ids = {s.step_id for s in self.steps}
        for edge in self.edges:
            if edge.from_step not in step_ids:
                raise ValueError(f"Edge from_step '{edge.from_step}' is not a step_id in steps")
            if edge.to_step not in step_ids:
                raise ValueError(f"Edge to_step '{edge.to_step}' is not a step_id in steps")
        return self


# ---------------------------------------------------------------------------
# Workflow Intent — extracted from user's natural language request
# ---------------------------------------------------------------------------


class WorkflowIntent(BaseModel):
    """Structured intent extracted from user's natural language request."""

    description: str = Field(description="Original user request")
    trigger: TriggerConfig = Field(description="Detected trigger type and config")
    data_objects: list[str] = Field(default_factory=list, description="Zuora objects mentioned")
    operations: list[str] = Field(default_factory=list, description="Operations detected")
    api_urls: list[str] = Field(default_factory=list, description="API URLs for Callout tasks")
    content_urls: list[str] = Field(
        default_factory=list, description="URLs for inclusion in emails"
    )
    conditions: list[str] = Field(default_factory=list, description="Conditions mentioned")
    missing_info: list[str] = Field(
        default_factory=list, description="Information that needs clarification"
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score (0-1)")
