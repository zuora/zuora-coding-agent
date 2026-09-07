"""Normalize LLM plan config from human-friendly shapes to Zuora wire format.

The planning LLM naturally outputs intuitive shapes:
  - fields as {"Invoice": ["Id", "Balance"]}  (array of field names)
  - headers as [{"key": "...", "value": "..."}]
  - retry_rules as {"retry_count": 3, ...}  (ints not strings)
  - email nested correctly or flattened

The manifest/API expects:
  - fields as {"Invoice": {"Id": "true", "Balance": "true"}} (SOAP-style)
  - headers as JSON string
  - retry_rules as {"retry_count": "3", ...}  (strings)
  - email as nested dict with to/from/subject/template

This module bridges the gap. Run normalize_plan() BEFORE Pydantic validation
and before the template engine processes tasks.
"""

from __future__ import annotations

import json
import re

# Task types that must use call_type="REST" in the assembled task JSON
REST_ONLY_TASK_TYPES = frozenset({"Suspend", "Resume", "Cancel", "InvoiceGenerate"})

# Canonical If-task branch outputs use capitalized True/False (UI default).
_IF_BRANCH_ELSE_FALSE = re.compile(
    r"(\{%\s*else\s*%\})\s*false\s*(\{%\s*endif)",
    re.IGNORECASE,
)
_IF_BRANCH_TRUE = re.compile(
    r"(\{%\s*if\b.*?\s*%\})\s*true\s*(\{%\s*else\s*%\})",
    re.IGNORECASE | re.DOTALL,
)

# Task types where the model expects fields.<wrapper>.<key> but the LLM often
# outputs flat fields.<key>.  (wrapper_key, frozenset of flat keys that belong
# under wrapper)
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


def _wrap_flat_fields_if_needed(params: dict, action_type: str) -> None:
    """If params has flat fields but model expects fields.<wrapper>.<key>, wrap under wrapper."""
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


def _normalize_trigger(plan_data: dict) -> None:
    """Coerce intent-shaped triggers to WorkflowPlan wire shape."""
    from workflow_engine.workflow_reference.event_parameters import coerce_event_names_list

    trigger = plan_data.get("trigger")
    if not isinstance(trigger, dict):
        return
    names = coerce_event_names_list(trigger.get("event_names"))
    if names:
        trigger["event_names"] = names


def normalize_plan(plan_data: dict) -> dict:
    """Normalize all tasks in a plan dict in-place. Returns the same dict."""
    _normalize_trigger(plan_data)
    for task in plan_data.get("tasks", []):
        normalize_task(task)
    return plan_data


def normalize_task(task: dict) -> None:
    """Normalize a single task's parameters in-place."""
    action_type = task.get("action_type", "")
    params = task.get("parameters")
    if not params or not isinstance(params, dict):
        return

    # --- Wrap flat fields under expected wrapper key ---
    if action_type in FLAT_FIELDS_WRAPPER:
        _wrap_flat_fields_if_needed(params, action_type)

    # --- Fields normalization (Query, Export, Data::Aqua, Data::Link) ---
    if action_type in ("Query", "Export", "Data::Aqua", "Data::Link"):
        _normalize_query_export_fields(params, task.get("object"))

    # --- Fields normalization for CRUD ---
    if action_type in ("Create", "Update"):
        _normalize_crud_fields(params, task.get("object"))

    # --- Email normalization ---
    if action_type == "Email":
        _normalize_email(params, task)

    # --- Callout normalization ---
    if action_type in ("Callout", "AsynchronousCallout"):
        _normalize_callout(params)

    # --- Retry rules: int values to strings ---
    if "retry_rules" in params:
        _stringify_retry_rules(params)

    # --- Headers normalization ---
    if "headers" in params and isinstance(params["headers"], (list, dict)):
        if action_type in ("Callout", "AsynchronousCallout"):
            _normalize_callout_headers(params)
        elif isinstance(params["headers"], (list, dict)):
            params["headers"] = json.dumps(params["headers"])

    # --- Authorization: keep as dict for Callout (Rails stores as {"type": "none"}) ---
    # No stringification needed; Rails reads it as a hash directly.

    # --- If clause: ensure it's a string with canonical True/False branch literals ---
    if action_type == "If" and "if_clause" in params:
        if not isinstance(params["if_clause"], str):
            params["if_clause"] = str(params["if_clause"])
        params["if_clause"] = _normalize_if_clause(params["if_clause"])

    # --- Logic::Case: ensure case_condition values are strings ---
    if action_type == "Logic::Case" and "case_condition" in params:
        cc = params["case_condition"]
        if isinstance(cc, dict):
            params["case_condition"] = {k: str(v) for k, v in cc.items()}
        elif isinstance(cc, (list, str)):
            pass
        else:
            params["case_condition"] = json.dumps(cc)

    # --- REST-only call_type ---
    if action_type in REST_ONLY_TASK_TYPES:
        task.setdefault("call_type", "REST")


def _normalize_query_export_fields(params: dict, object_name: str | None) -> None:
    """Convert fields from array or flat dict to SOAP-style {Object: {Field: 'true'}}."""
    fields = params.get("fields")
    if fields is None:
        return

    if isinstance(fields, str):
        try:
            fields = json.loads(fields)
        except (json.JSONDecodeError, ValueError):
            return
        params["fields"] = fields

    if isinstance(fields, list) and object_name:
        params["fields"] = {object_name: {f: "true" for f in fields if isinstance(f, str)}}
        return

    if isinstance(fields, dict):
        normalized: dict[str, dict] = {}
        for obj_key, obj_val in fields.items():
            if isinstance(obj_val, list):
                normalized[obj_key] = {f: "true" for f in obj_val if isinstance(f, str)}
            elif isinstance(obj_val, dict):
                soap_fields: dict[str, str] = {}
                for fname, fval in obj_val.items():
                    if fval == "true" or fval is True:
                        soap_fields[fname] = "true"
                    elif isinstance(fval, dict) and len(fval) == 0:
                        soap_fields[fname] = "true"
                    else:
                        soap_fields[fname] = str(fval) if fval is not None else "true"
                normalized[obj_key] = soap_fields
            else:
                normalized[obj_key] = obj_val
        params["fields"] = normalized


def _normalize_crud_fields(params: dict, object_name: str | None) -> None:
    """Ensure CRUD fields are nested under the object name."""
    fields = params.get("fields")
    if not isinstance(fields, dict) or not fields:
        return
    if not object_name:
        return
    first_key = next(iter(fields))
    if first_key == object_name:
        return
    if isinstance(fields.get(first_key), dict):
        return
    params["fields"] = {object_name: fields}


def _normalize_email(params: dict, task: dict) -> None:
    """Normalize email params into the nested {email: {to, from, subject, template}} shape."""
    email = params.get("email")

    if isinstance(email, str):
        try:
            email = json.loads(email)
            params["email"] = email
        except (json.JSONDecodeError, ValueError):
            return

    if not isinstance(email, dict):
        to = params.pop("to", None) or ["{{Data.BillToContact.WorkEmail}}"]
        from_addr = (
            params.pop("from_email", None) or params.pop("from", None) or "workflow@zuora.com"
        )
        subject = params.pop("subject", None) or "Notification"
        template = params.pop("template", None) or ""
        name = params.pop("sender_name", None) or task.get("name", "")
        if not isinstance(to, list):
            to = [to]
        params["email"] = {
            "to": to,
            "from": from_addr,
            "name": name,
            "subject": subject,
            "template": template,
        }
        return

    if not isinstance(email.get("to"), list):
        to = email.get("to")
        email["to"] = [to] if to else ["{{Data.BillToContact.WorkEmail}}"]
    email.setdefault("from", "workflow@zuora.com")
    email.setdefault("subject", "Notification")
    email.setdefault("template", "")
    email.setdefault("name", task.get("name", ""))


def _normalize_callout_headers(params: dict) -> None:
    """Ensure Callout headers are in Rails dict format: [{"key": "...", "value": "..."}].

    Rails stores and expects headers as list of ``{"key": K, "value": V}`` objects.
    The LLM may output dicts with variant keys (``name``, ``header``) or may output
    colon-separated strings — normalise everything to the canonical shape.
    """
    headers = params.get("headers")
    # Convert plain dict (LLM drift: {"Content-Type": "application/json"})
    if isinstance(headers, dict):
        params["headers"] = [{"key": k, "value": str(v)} for k, v in headers.items()]
        return
    if not isinstance(headers, list):
        return
    normalized: list[dict[str, str]] = []
    for item in headers:
        if isinstance(item, dict):
            key = item.get("key") or item.get("name") or item.get("header") or ""
            value = item.get("value") or ""
            if key:
                normalized.append({"key": key, "value": value})
        elif isinstance(item, str) and ":" in item:
            k, _, v = item.partition(":")
            normalized.append({"key": k.strip(), "value": v.strip()})
        elif isinstance(item, str) and item.strip():
            normalized.append({"key": item.strip(), "value": ""})
    params["headers"] = normalized


def _normalize_callout(params: dict) -> None:
    """Normalize callout params (retry_rules, validation, body)."""
    if "raw_body" in params and isinstance(params["raw_body"], (dict, list)):
        params["raw_body"] = json.dumps(params["raw_body"], indent=2)

    if "body" in params and "raw_body" not in params:
        body = params.pop("body")
        if isinstance(body, (dict, list)):
            params["raw_body"] = json.dumps(body, indent=2)
        elif isinstance(body, str):
            params["raw_body"] = body

    validation = params.get("validation")
    if isinstance(validation, dict):
        for k in ("replace", "zuora_call", "validate_response", "include_response_code"):
            if k in validation and isinstance(validation[k], bool):
                validation[k] = "true" if validation[k] else "false"


def _stringify_retry_rules(params: dict) -> None:
    """Convert retry_rules int values to strings."""
    rr = params.get("retry_rules")
    if not isinstance(rr, dict):
        return
    for key in ("retry_count", "retry_window", "current_retry_count"):
        if key in rr and isinstance(rr[key], (int, float)):
            rr[key] = str(int(rr[key]))


def _normalize_if_clause(clause: str) -> str:
    """Rewrite lowercase true/false branch outputs to canonical True/False."""
    updated = _IF_BRANCH_ELSE_FALSE.sub(r"\1False\2", clause)
    return _IF_BRANCH_TRUE.sub(r"\1True\2", updated)
