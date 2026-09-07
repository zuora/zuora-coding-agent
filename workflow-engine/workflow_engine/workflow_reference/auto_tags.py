"""Auto-tag finalization: populate ``task.tags`` with Liquid references
to the individual object a task is working with (e.g.
``{{Data.Invoice.Id}}``, ``{{Data.Invoice.InvoiceNumber}}``).

Tags let operators search execution history for the specific object(s) a
task processed. They are only meaningful when the task is operating on a
single, identifiable object — inside an Iterate body (one element per
loop), or on a single-object-event-triggered workflow where the event
payload provides the Id + human-readable number.

Algorithm (per task):

1. Determine the "individual object":
   * Iterate body members: the Iterate task's resolved ``object``.
   * Tasks outside any Iterate body: when the workflow trigger is a
     single-object event whose payload exposes the object, use that
     event object. Otherwise skip.
2. Confirm the tag references are available at this task's execution
   point via a :class:`DataFlowTracker` replay. Without both ``Id`` and
   the chosen number field being visible, skip.
3. Emit ``tags = ["{{Data.<Obj>.Id}}", "{{Data.<Obj>.<NumberField>}}"]``.
4. Leave existing non-empty ``tags`` untouched.

The number-field map is intentionally conservative — we only auto-tag
objects whose canonical human-readable number is well-known at the
platform level. Custom objects, unusual objects, and one-off shapes
(``Contact`` in particular has no canonical number field and falls back
to ``Id`` only).
"""

from __future__ import annotations

from typing import Any

from workflow_engine.workflow_reference.data_flow import DataFlowTracker
from workflow_engine.workflow_reference.event_parameters import (
    EVENT_BASE_OBJECTS,
    seed_event_data_paths,
)
from workflow_engine.workflow_reference.plan_validator import iterate_body_map

# Canonical human-readable number field per Zuora object. Keep this list
# conservative — we only auto-tag objects whose number field is a platform
# invariant.
OBJECT_NUMBER_FIELD: dict[str, str] = {
    "Invoice": "InvoiceNumber",
    "CreditMemo": "CreditMemoNumber",
    "DebitMemo": "DebitMemoNumber",
    "Payment": "PaymentNumber",
    "Refund": "RefundNumber",
    "PaymentRun": "PaymentRunNumber",
    "BillRun": "BillRunNumber",
    "BillingRun": "BillRunNumber",
    "Subscription": "SubscriptionNumber",
    "Order": "OrderNumber",
    "Account": "AccountNumber",
    "RatePlan": "Name",
    "Product": "SKU",
}

# Task types whose execution is keyed to the single object currently in
# scope (inside an Iterate body, or on a single-object event trigger).
# Callout / AsynchronousCallout are included — an Iterate body callout
# operates on one object per iteration; outside Iterate, a callout tied
# to a single-object event still references that event's object.
_SINGLE_OBJECT_TASK_TYPES: frozenset[str] = frozenset(
    {
        "Callout",
        "AsynchronousCallout",
        "Email",
        "Create",
        "Update",
        "Delete",
        "Attachment",
        "Notification::Comment",
        "Workflow::Trigger",
        "Billing::ElectronicPayment",
        "Billing::PostInvoice",
        "Billing::Cancel",
        "Billing::Reverse",
        "Billing::CreditBalanceAdjustment",
        "Billing::ApplyPayment",
        "Billing::UnapplyPayment",
        "Billing::Refund",
        "Suspend",
        "Resume",
        "Cancel",
        "Activate",
        "InvoiceGenerate",
        "WriteOff",
    }
)


def _strip_data_prefix(obj: str) -> str:
    """Normalize ``Data.Invoice`` / ``Invoice`` / ``Data.Files`` → ``Invoice``."""
    if not obj:
        return ""
    if obj.startswith("Data."):
        return obj[len("Data.") :]
    return obj


def _build_iterate_context(plan_data: dict) -> tuple[dict[int, str], dict[int, int]]:
    """Return two maps:

    * ``iterate_object_by_id``: ``{iterate_task_id: Data-prefix-stripped object}``.
    * ``body_task_to_iterate``: ``{body_task_id: iterate_task_id}``.
    """
    tasks = plan_data.get("tasks") or []
    linkages = plan_data.get("linkages") or []
    task_by_id: dict[int, dict[str, Any]] = {
        t["id"]: t for t in tasks if isinstance(t.get("id"), int)
    }

    iterate_object_by_id: dict[int, str] = {}
    for tid, t in task_by_id.items():
        if t.get("action_type") == "Iterate":
            iterate_object_by_id[tid] = _strip_data_prefix(str(t.get("object") or ""))

    body_map = iterate_body_map(linkages, task_by_id)
    body_task_to_iterate: dict[int, int] = {}
    for iter_id, body in body_map.items():
        for bid in body:
            body_task_to_iterate.setdefault(bid, iter_id)
    return iterate_object_by_id, body_task_to_iterate


def _single_object_event_target(plan_data: dict) -> str:
    """Return the canonical PRIMARY object for the trigger, or ``""``.

    Uses :data:`EVENT_BASE_OBJECTS` as the source of truth — every supported
    event names one primary object (``InvoicePosted`` -> ``Invoice``,
    ``PaymentProcessed`` -> ``Payment``, etc.). Secondary payload objects
    (``Account`` / ``BillToContact`` on ``InvoicePosted``) are not
    considered primary.

    When multiple event names are bound to one workflow, they must all
    share the same primary object for auto-tagging to kick in — otherwise
    the tasks have no single concrete object to identify.
    """
    trigger = plan_data.get("trigger") or {}
    if trigger.get("type") != "event":
        return ""
    events = trigger.get("event_names") or []
    if not events:
        return ""
    primaries: set[str] = set()
    for name in events:
        if name in EVENT_BASE_OBJECTS:
            primaries.add(EVENT_BASE_OBJECTS[name][0])
    if len(primaries) != 1:
        return ""
    (obj,) = primaries
    if obj not in OBJECT_NUMBER_FIELD:
        return ""
    return obj


def _tag_object_for_task(
    task: dict,
    iterate_object_by_id: dict[int, str],
    body_task_to_iterate: dict[int, int],
    event_target_object: str,
) -> str:
    """Return the canonical object name to tag with, or ``""`` to skip."""
    action = task.get("action_type")
    if action not in _SINGLE_OBJECT_TASK_TYPES:
        return ""
    tid = task.get("id")
    if not isinstance(tid, int):
        return ""

    iterate_id = body_task_to_iterate.get(tid)
    if iterate_id is not None:
        obj = iterate_object_by_id.get(iterate_id, "")
        if obj and obj in OBJECT_NUMBER_FIELD:
            return obj
        return ""

    if event_target_object:
        return event_target_object
    return ""


def apply_auto_tags(plan_data: dict) -> list[str]:
    """Populate ``task["tags"]`` with ``{{Data.<Obj>.Id}}`` and
    ``{{Data.<Obj>.<NumberField>}}`` for every eligible task. Mutates the
    plan in place. Returns a list of human-readable info messages (one
    per task tagged, empty when nothing changed).
    """
    tasks: list[dict] = plan_data.get("tasks") or []
    if not tasks:
        return []

    iterate_object_by_id, body_task_to_iterate = _build_iterate_context(plan_data)
    event_target_object = _single_object_event_target(plan_data)

    tracker = DataFlowTracker()
    trigger = plan_data.get("trigger") or {}
    event_names = trigger.get("event_names") or []
    if event_names:
        event_paths = seed_event_data_paths(event_names)
        tracker.available |= event_paths
        # ``seed_event_data_paths`` populates ``available`` but not
        # ``selected_fields``. Mirror the paths so :meth:`is_field_selected`
        # reflects what the event actually exposes.
        for path in event_paths:
            parts = path.split(".")
            if len(parts) == 3:
                tracker.selected_fields.setdefault(parts[1], set()).add(parts[2])

    input_fields = plan_data.get("input_fields") or []
    if input_fields:
        tracker.add_input_fields(input_fields)

    messages: list[str] = []
    for task in tasks:
        existing = task.get("tags") or []
        has_user_tags = isinstance(existing, list) and any(
            isinstance(v, str) and v.strip() for v in existing
        )

        if not has_user_tags:
            target_obj = _tag_object_for_task(
                task,
                iterate_object_by_id,
                body_task_to_iterate,
                event_target_object,
            )
            if target_obj:
                number_field = OBJECT_NUMBER_FIELD.get(target_obj)
                id_available = _liquid_field_available(tracker, target_obj, "Id")
                number_available = bool(number_field) and _liquid_field_available(
                    tracker,
                    target_obj,
                    number_field,  # type: ignore[arg-type]
                )
                tags: list[str] = []
                if id_available:
                    tags.append(f"{{{{Data.{target_obj}.Id}}}}")
                if number_available:
                    tags.append(f"{{{{Data.{target_obj}.{number_field}}}}}")
                if tags:
                    task["tags"] = tags
                    messages.append(
                        f"Task '{task.get('name', '')}' (id={task.get('id')}): "
                        f"auto-tagged with {tags}."
                    )

        _replay_task(tracker, task)

    return messages


def _replay_task(tracker: DataFlowTracker, task: dict) -> None:
    """Advance the ``DataFlowTracker`` for a plan-shape task.

    Mirrors the config shape expected by :meth:`DataFlowTracker.after_task`
    (parameters merged up one level + ``id`` / ``object`` / ``placement``
    carried alongside). Matches the existing pattern used by
    :mod:`tools.build_workflow_definition` when it builds the data-payload
    trace.
    """
    parameters = task.get("parameters") or {}
    config = {
        **parameters,
        "id": task.get("id"),
        "object": task.get("object", ""),
        "placement": parameters.get("placement", ""),
    }
    tracker.after_task(
        task.get("action_type", ""),
        config,
        task.get("name", ""),
    )


def _liquid_field_available(
    tracker: DataFlowTracker,
    object_name: str,
    field_name: str,
) -> bool:
    """Tag-specific availability check.

    Unlike :meth:`DataFlowTracker.is_field_selected`, this returns ``True``
    only when the field is known to be present — via an explicit selection
    (``selected_fields``) OR a seeded ``Data.<Obj>.<Field>`` path in
    ``available``. Event-payload seeding covers both paths and selected
    fields for the object; Query / Export ``after_task`` bookkeeping covers
    objects produced mid-workflow. Standard-field fallbacks (``Id``,
    ``Name``, etc.) are honored for ``Id`` since every Zuora record has
    one, but numeric-number fields like ``InvoiceNumber`` must be
    explicitly present.
    """
    if not object_name or not field_name:
        return False
    if f"Data.{object_name}.{field_name}" in tracker.available:
        return True
    selected = tracker.selected_fields.get(object_name)
    if selected is not None and field_name in selected:
        return True
    # ``Id`` is the universal Zuora primary key — allow it even if the
    # caller did not explicitly declare it in the upstream select list.
    if field_name == "Id" and (
        object_name in tracker.selected_fields or f"Data.{object_name}" in tracker.available
    ):
        return True
    return False
