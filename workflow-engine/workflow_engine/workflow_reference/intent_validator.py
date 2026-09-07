"""Intent validator — pure validation of LLM-provided structured workflow intent.

The LLM produces structured intent JSON (conforming to the WorkflowIntent template
in the system prompt). This module validates that intent against reference data
(VALID_EVENT_NAMES, EVENT_PAYLOAD_OBJECTS, TASK_CATALOG, KB objects) and auto-wires
event_parameters.

It classifies missing-information signals the LLM surfaces into two buckets:

  - ``blockers``    — the LLM MUST ask the user (no reasonable default)
  - ``assumptions`` — auto-filled with a reasonable default; the LLM MUST disclose
                     these to the user in the plan summary

No regex, no NL parsing, no keyword maps live in this module. The LLM owns
natural-language understanding upstream; this module performs pure validation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from workflow_engine.workflow_reference.event_parameters import (
    EVENT_BASE_OBJECTS,
    VALID_EVENT_NAMES,
    generate_event_parameters,
    get_payload_objects,
    is_multi_object_event,
    is_run_event,
    suggest_event_name,
)

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

VALID_TRIGGER_TYPES: frozenset[str] = frozenset({"event", "scheduled", "ondemand", "callout"})

# Tasks that require an object_id and cannot reasonably be defaulted
_ID_REQUIRED_TASKS: frozenset[str] = frozenset(
    {
        "Update",
        "Delete",
        "Suspend",
        "Resume",
        "Cancel",
        "NewProduct",
        "RemoveProduct",
    }
)


def _load_kb_objects() -> frozenset[str]:
    """Parse the ``zuora_objects_and_fields.md`` KB file for a set of valid object names."""
    kb_path = Path(__file__).resolve().parents[2] / "knowledge_base" / "zuora_objects_and_fields.md"
    if not kb_path.exists():
        return frozenset()
    objects: set[str] = set()
    for line in kb_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## ") and len(line) > 3:
            name = line[3:].strip()
            if name and name[0].isupper():
                objects.add(name)
    return frozenset(objects)


KB_OBJECTS: frozenset[str] = _load_kb_objects()


# ---------------------------------------------------------------------------
# Missing-info signal classification
# ---------------------------------------------------------------------------

# Signals the LLM surfaces that require a blocker question (no reasonable default).
BLOCKER_SIGNALS: frozenset[str] = frozenset(
    {
        "missing_callout_url_no_context",
        "missing_event_name_ambiguous_3plus",
        "missing_object_id_no_trigger_context",
        "missing_approver_emails_with_no_fallback",
        "missing_custom_field_name_no_assumption",
        "missing_data_object_no_context",
        "missing_schedule_cadence",
    }
)

# Signals that map to deterministic auto-fill values ("applied" assumptions —
# the validator fills these in directly and records the assumption).
_APPLIED_DEFAULTS: dict[str, dict[str, Any]] = {
    "missing_schedule_timezone": {
        "target": "trigger.timezone",
        "value": "UTC",
        "reason": "No timezone specified; defaulted to UTC. Tell me a region/timezone to change.",
        "confidence": 0.7,
    },
    "missing_zero_query_proceed": {
        "target": "parameters.zero_query_proceed",
        "value": False,
        "reason": "Default Query behavior: do not proceed on empty result.",
        "confidence": 0.9,
    },
    "missing_zero_result_stop": {
        "target": "parameters.zero_result_stop",
        "value": True,
        "reason": "Default Export behavior: stop workflow on empty result.",
        "confidence": 0.9,
    },
    "missing_callout_method": {
        "target": "parameters.method",
        "value": "POST",
        "reason": "No HTTP method specified; defaulted to POST.",
        "confidence": 0.85,
    },
    "missing_callout_headers": {
        "target": "parameters.headers",
        "value": [{"key": "Content-Type", "value": "application/json"}],
        "reason": "No headers specified; defaulted to application/json.",
        "confidence": 0.85,
    },
    "missing_zip_setting": {
        "target": "parameters.zip",
        "value": False,
        "reason": "No zip preference; defaulted to false.",
        "confidence": 0.95,
    },
}

# Signals the LLM should synthesize a value for (too context-dependent to apply
# here). The validator records them as assumptions to disclose to the user.
_SUGGESTED_DEFAULTS: dict[str, dict[str, Any]] = {
    "missing_email_subject": {
        "suggestion": "Zuora Notification: <descriptive>",
        "reason": "No email subject provided; compose from workflow context.",
        "confidence": 0.8,
    },
    "missing_email_body": {
        "suggestion": "__AUTO_COMPOSE__",
        "reason": "No email body provided; compose from available Liquid fields.",
        "confidence": 0.7,
    },
    "missing_fields_list": {
        "suggestion": "__DERIVE_FROM_LIQUID_PLUS_ID__",
        "reason": (
            "No explicit field list; select Id plus any fields referenced by "
            "downstream Liquid references."
        ),
        "confidence": 0.85,
    },
    "missing_call_type": {
        "suggestion": "__INFER_FROM_TRIGGER__",
        "reason": (
            "No call_type given; infer from trigger (run-events -> BATCH, "
            "other events -> REALTIME, scheduled -> ASYNC)."
        ),
        "confidence": 0.95,
    },
    "missing_filter_for_common_term": {
        "suggestion": "__COMMON_FILTER_DEFAULT__",
        "reason": (
            "Map common terms to standard filters (active -> Status='Active', "
            "overdue -> DueDate < today AND Balance > 0, etc.)."
        ),
        "confidence": 0.75,
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_intent(intent: dict[str, Any]) -> dict[str, Any]:
    """Validate a structured ``WorkflowIntent`` dict produced by the LLM.

    Args:
        intent: LLM-produced intent with at least ``trigger`` and optionally
            ``event_fields_by_object``, ``data_objects``, ``final_tasks``,
            ``missing_info``, ``business_outcome``, etc.

    Returns:
        A dict with keys:
          - ``ok``          : True if no blockers and all structural fields valid
          - ``intent``      : the (possibly-corrected) intent
          - ``event_parameters``: auto-wired event_parameters for the trigger
          - ``corrections`` : list of ``{field, from, to, reason}`` normalizations applied
          - ``blockers``    : list of ``{signal, message}`` questions the LLM MUST ask
          - ``assumptions`` : list of ``{field, value, reason, confidence}`` entries
                              applied or suggested (LLM MUST disclose to user)
          - ``errors``      : list of structural errors (bad trigger type, unknown
                              event, etc.) — these are hard failures, not soft signals
    """
    result: dict[str, Any] = {
        "ok": True,
        "intent": {},
        "event_parameters": [],
        "corrections": [],
        "blockers": [],
        "assumptions": [],
        "errors": [],
    }

    if not isinstance(intent, dict):
        result["ok"] = False
        result["errors"].append(
            {
                "path": "intent",
                "code": "INVALID_TYPE",
                "message": "intent must be a JSON object",
            }
        )
        return result

    working: dict[str, Any] = dict(intent)
    result["intent"] = working

    _validate_trigger(working, result)
    _validate_data_objects(working, result)
    _classify_missing_info(working, result)

    if working.get("trigger", {}).get("type") == "event":
        _auto_wire_event_parameters(working, result)

    result["ok"] = not result["errors"] and not result["blockers"]
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_trigger(intent: dict[str, Any], result: dict[str, Any]) -> None:
    trigger = intent.get("trigger")
    if not isinstance(trigger, dict):
        result["errors"].append(
            {
                "path": "trigger",
                "code": "MISSING_TRIGGER",
                "message": "intent.trigger is required and must be an object",
            }
        )
        return

    ttype = trigger.get("type")
    if ttype not in VALID_TRIGGER_TYPES:
        result["errors"].append(
            {
                "path": "trigger.type",
                "code": "INVALID_TRIGGER_TYPE",
                "message": (
                    f"trigger.type must be one of {sorted(VALID_TRIGGER_TYPES)}; " f"got {ttype!r}"
                ),
            }
        )
        return

    if ttype == "event":
        _validate_event_trigger(trigger, result)
    elif ttype == "scheduled":
        _validate_scheduled_trigger(trigger, result)


def _coerce_event_names(trigger: dict[str, Any], result: dict[str, Any]) -> Any:
    """Normalize event_names to a single string, recording a correction if a list was given."""
    raw = trigger.get("event_names")
    if not isinstance(raw, list):
        return raw
    if not raw:
        return None
    normalized = raw[0]
    reason = (
        "event_names must be a single string; extracted first element"
        if len(raw) == 1
        else "event_names must be a single string; using first of multiple values"
    )
    result["corrections"].append(
        {
            "path": "trigger.event_names",
            "from": raw,
            "to": normalized,
            "reason": reason,
        }
    )
    trigger["event_names"] = normalized
    return normalized


def _validate_event_trigger(trigger: dict[str, Any], result: dict[str, Any]) -> None:
    event_name = _coerce_event_names(trigger, result)
    if not event_name:
        result["errors"].append(
            {
                "path": "trigger.event_names",
                "code": "MISSING_EVENT_NAME",
                "message": (
                    "trigger.event_names is required for event triggers. Use one of "
                    f"{VALID_EVENT_NAMES[:5]}... (see lookup_workflow_reference(topic='events'))"
                ),
            }
        )
        return

    if event_name not in EVENT_BASE_OBJECTS:
        suggestion = suggest_event_name(event_name)
        if suggestion:
            result["corrections"].append(
                {
                    "path": "trigger.event_names",
                    "from": event_name,
                    "to": suggestion,
                    "reason": f"Fuzzy-matched {event_name!r} to valid event {suggestion!r}",
                }
            )
            trigger["event_names"] = suggestion
            event_name = suggestion
        else:
            result["errors"].append(
                {
                    "path": "trigger.event_names",
                    "code": "UNKNOWN_EVENT_NAME",
                    "message": (
                        f"event_name {event_name!r} is not a valid Zuora event. "
                        f"Valid events: {', '.join(VALID_EVENT_NAMES[:8])}..."
                    ),
                }
            )
            return

    fields_by_object = trigger.get("event_fields_by_object") or trigger.get("event_fields")
    if fields_by_object is None:
        return

    if isinstance(fields_by_object, list):
        primary_obj, _ = EVENT_BASE_OBJECTS[event_name]
        trigger["event_fields_by_object"] = {primary_obj: list(fields_by_object)}
        fields_by_object = trigger["event_fields_by_object"]

    if not isinstance(fields_by_object, dict):
        result["errors"].append(
            {
                "path": "trigger.event_fields_by_object",
                "code": "INVALID_TYPE",
                "message": (
                    "event_fields_by_object must be a mapping of " "{object_name: [field_name,...]}"
                ),
            }
        )
        return

    valid_objects = set(get_payload_objects(event_name))
    unknown_objects = [obj for obj in fields_by_object.keys() if obj not in valid_objects]
    if unknown_objects:
        result["errors"].append(
            {
                "path": "trigger.event_fields_by_object",
                "code": "UNKNOWN_PAYLOAD_OBJECT",
                "message": (
                    f"Event {event_name!r} does not expose objects {unknown_objects}. "
                    f"Exposed objects: {sorted(valid_objects)}"
                ),
            }
        )


def _validate_scheduled_trigger(trigger: dict[str, Any], result: dict[str, Any]) -> None:
    schedule = trigger.get("schedule") or trigger.get("scheduled_interval")
    if not schedule:
        result["blockers"].append(
            {
                "signal": "missing_schedule_cadence",
                "message": (
                    "Scheduled trigger needs a cron expression. Example: "
                    "'0 9 * * *' for daily at 9am. How often should this run?"
                ),
            }
        )


def _validate_data_objects(intent: dict[str, Any], result: dict[str, Any]) -> None:
    objs = intent.get("data_objects")
    if not isinstance(objs, list):
        return

    if not KB_OBJECTS:
        return

    kb_lower = {obj.lower(): obj for obj in KB_OBJECTS}
    for i, obj in enumerate(objs):
        if not isinstance(obj, str) or not obj:
            continue
        if obj in KB_OBJECTS:
            continue
        canonical = kb_lower.get(obj.lower())
        if canonical and canonical != obj:
            result["corrections"].append(
                {
                    "path": f"data_objects[{i}]",
                    "from": obj,
                    "to": canonical,
                    "reason": "Normalized case to match KB object name",
                }
            )
            objs[i] = canonical


def _auto_wire_event_parameters(intent: dict[str, Any], result: dict[str, Any]) -> None:
    trigger = intent.get("trigger", {})
    event_name = trigger.get("event_names")
    if not event_name or event_name not in EVENT_BASE_OBJECTS:
        return

    fields_by_object = trigger.get("event_fields_by_object")
    if not fields_by_object and is_multi_object_event(event_name):
        fields_by_object = _default_multi_object_fields(event_name)
        trigger["event_fields_by_object"] = fields_by_object
        result["assumptions"].append(
            {
                "field": "trigger.event_fields_by_object",
                "value": fields_by_object,
                "reason": (
                    f"Event {event_name} exposes multiple objects; defaulted to common "
                    f"fields for each. Override if you need different fields."
                ),
                "confidence": 0.75,
            }
        )

    ep = generate_event_parameters(event_name, fields_by_object=fields_by_object)
    result["event_parameters"] = ep
    trigger["event_parameters"] = ep


def _default_multi_object_fields(event_name: str) -> dict[str, list[str]]:
    """Default per-object field lists for a multi-object event.

    Uses the event's primary object plus the common companion objects
    (Account, BillToContact) with their typical fields.
    """
    primary_obj, _ = EVENT_BASE_OBJECTS[event_name]
    payload_objects = get_payload_objects(event_name)
    defaults: dict[str, list[str]] = {}

    primary_field_defaults = {
        "Invoice": ["Id", "InvoiceNumber", "Amount", "Balance", "DueDate"],
        "Payment": ["Id", "PaymentNumber", "Amount", "Status", "EffectiveDate"],
        "CreditMemo": ["Id", "MemoNumber", "Amount"],
        "DebitMemo": ["Id", "MemoNumber", "Amount"],
        "Subscription": ["Id", "Name", "Status", "TermStartDate", "TermEndDate"],
        "Amendment": ["Id", "Name", "Type", "Status"],
        "Refund": ["Id", "RefundNumber", "Amount", "Status"],
    }
    companion_field_defaults = {
        "Account": ["Id", "Name", "AccountNumber", "Currency"],
        "BillToContact": ["WorkEmail", "FirstName", "LastName"],
        "Subscription": ["Id", "Name", "Status"],
    }

    for obj in payload_objects:
        if obj == primary_obj:
            defaults[obj] = primary_field_defaults.get(obj, ["Id"])
        else:
            defaults[obj] = companion_field_defaults.get(obj, ["Id"])
    return defaults


def _classify_missing_info(intent: dict[str, Any], result: dict[str, Any]) -> None:
    """Split the LLM-provided ``missing_info`` list into blockers vs assumptions."""
    missing = intent.get("missing_info")
    if not isinstance(missing, list):
        return

    trigger_type = (intent.get("trigger") or {}).get("type")
    event_name = (intent.get("trigger") or {}).get("event_names", "")

    for signal in missing:
        if not isinstance(signal, str):
            continue
        if signal in BLOCKER_SIGNALS:
            result["blockers"].append(
                {
                    "signal": signal,
                    "message": _describe_blocker(signal),
                }
            )
            continue

        if signal in _APPLIED_DEFAULTS:
            spec = _APPLIED_DEFAULTS[signal]
            if signal == "missing_schedule_timezone" and trigger_type == "scheduled":
                trigger = intent.setdefault("trigger", {})
                trigger.setdefault("timezone", spec["value"])
            result["assumptions"].append(
                {
                    "field": spec["target"],
                    "value": spec["value"],
                    "reason": spec["reason"],
                    "confidence": spec["confidence"],
                }
            )
            continue

        if signal in _SUGGESTED_DEFAULTS:
            spec = _SUGGESTED_DEFAULTS[signal]
            value = spec["suggestion"]
            if signal == "missing_call_type":
                value = _infer_call_type(trigger_type, event_name)
            result["assumptions"].append(
                {
                    "field": signal,
                    "value": value,
                    "reason": spec["reason"],
                    "confidence": spec["confidence"],
                }
            )
            continue

        result["assumptions"].append(
            {
                "field": signal,
                "value": None,
                "reason": "Unknown missing_info signal; treated as soft default. Disclose to user.",
                "confidence": 0.5,
            }
        )


def _infer_call_type(trigger_type: Optional[str], event_name: str) -> str:
    """Infer call_type from trigger type + event (for the missing_call_type default)."""
    if trigger_type == "scheduled":
        return "ASYNC"
    if trigger_type == "event" and is_run_event(event_name):
        return "BATCH"
    if trigger_type == "event":
        return "REALTIME"
    return "ASYNC"


def _describe_blocker(signal: str) -> str:
    messages = {
        "missing_callout_url_no_context": (
            "No external URL was provided for the Callout task and none can be "
            "inferred from context. Please provide the target URL."
        ),
        "missing_event_name_ambiguous_3plus": (
            "Three or more equally-plausible event names match the request. "
            "Please specify which event should trigger the workflow."
        ),
        "missing_object_id_no_trigger_context": (
            "An Update/Delete/Suspend task needs an object_id but no trigger data "
            "or upstream task provides one. Please specify how to identify the target."
        ),
        "missing_approver_emails_with_no_fallback": (
            "Approval task needs approver emails and no fallback was provided. "
            "Who should approve?"
        ),
        "missing_custom_field_name_no_assumption": (
            "A custom field was referenced ambiguously. Please provide the exact "
            "custom field name (e.g., Account.OverdueFlag__c)."
        ),
        "missing_data_object_no_context": (
            "The workflow references 'data' but no specific Zuora object can be "
            "inferred. Please specify which object to operate on."
        ),
        "missing_schedule_cadence": (
            "Scheduled trigger needs a cron expression. How often should this run?"
        ),
    }
    return messages.get(
        signal,
        f"Required information missing: {signal}",
    )
