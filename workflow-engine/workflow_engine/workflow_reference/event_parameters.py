"""
Zuora Workflow event parameter generation for workflow.parameters.event_parameters.

Maps workflow UI event names to Data.* object names and default Id params, aligned with
Rails workflow exports and ~/Workspace/developer-agent/workflow_agent/orchestration/nodes/intent.py.

The defaultEvents list in the Rails UI (WorkflowDefinitionForm.js) is the source of truth
for standard event names. Custom events are tenant-defined via the Events API.
"""

from __future__ import annotations

import re
from typing import Any, Optional


def coerce_event_names_list(raw: Any) -> list[str]:
    """Return ``event_names`` as a list of non-empty strings.

    WorkflowIntent uses a single string; WorkflowPlan uses a list. Callers that
    iterate ``trigger.event_names`` must coerce first — iterating a bare string
    walks characters (e.g. ``"BillingRunCompletion"`` → ``B``, ``i``, ``l``, …).
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        stripped = raw.strip()
        return [stripped] if stripped else []
    if isinstance(raw, list):
        return [n.strip() for n in raw if isinstance(n, str) and n.strip()]
    return []

# (Data object name for params.object, event payload path prefix for Liquid placeholders)
# Data object name → used in Data.* references: Data.{object}.{key}
# Payload path prefix → used in event_parameters value: <{path}.{key}>
# All 32 standard Zuora billing events from knowledge_base/zuora_events_fields.md
EVENT_BASE_OBJECTS: dict[str, tuple[str, str]] = {
    # --- Batch (run) events ---
    "BillingRunCompletion": ("BillingRun", "BillRun"),
    "PaymentRunCompletion": ("PaymentRun", "PaymentRun"),
    "JournalRunCompletion": ("JournalRun", "JournalRun"),
    # --- Realtime events ---
    "AmendmentProcessed": ("Amendment", "Amendment"),
    "AquaNotification": ("Aqua", "Aqua"),
    "CreditBalanceRefundProcessed": ("Refund", "Refund"),
    "CreditMemoCreated": ("CreditMemo", "CreditMemo"),
    "CreditMemoPosted": ("CreditMemo", "CreditMemo"),
    "CreditMemoRefundProcessed": ("Refund", "Refund"),
    "DataSourceOutputCompletion": ("Export", "Export"),
    "DebitMemoCreated": ("DebitMemo", "DebitMemo"),
    "DebitMemoPosted": ("DebitMemo", "DebitMemo"),
    "EmailCreditMemo": ("CreditMemo", "CreditMemo"),
    "EmailDebitMemo": ("DebitMemo", "DebitMemo"),
    "GatewayReconciliation": ("GatewayReconciliationJob", "GatewayReconciliationJob"),
    "InvoiceDue": ("Invoice", "Invoice"),
    "InvoicePosted": ("Invoice", "Invoice"),
    "InvoicesPastDueAccountSummary": ("Account", "Account"),
    "KeyDates": ("Subscription", "Subscription"),
    "ManualEmailForInvoice": ("Invoice", "Invoice"),
    "ManualEmailForPayment": ("Payment", "Payment"),
    "PaymentDeclined": ("Payment", "Payment"),
    "PaymentMethodClosed": ("DefaultPaymentMethod", "DefaultPaymentMethod"),
    "PaymentMethodExpiration": ("PaymentMethod", "PaymentMethod"),
    "PaymentMethodUpdated": ("DefaultPaymentMethod", "DefaultPaymentMethod"),
    "PaymentMethodUpdaterBatchCompleted": ("PMUBatch", "PMUBatch"),
    "PaymentMethodUpdaterBatchStarted": ("PMUBatch", "PMUBatch"),
    "PaymentProcessed": ("Payment", "Payment"),
    "PaymentRefundProcessed": ("Refund", "Refund"),
    "SubscriptionCreated": ("Subscription", "Subscription"),
    "TrialBalanceCompletion": ("AccountingPeriod", "AccountingPeriod"),
    "UpcomingRenewal": ("Subscription", "Subscription"),
}

# Events that expose multiple payload objects (object name -> path prefix).
EVENT_PAYLOAD_OBJECTS: dict[str, list[tuple[str, str]]] = {
    "PaymentProcessed": [
        ("Payment", "Payment"),
        ("Account", "Account"),
        ("BillToContact", "BillToContact"),
    ],
    "PaymentDeclined": [
        ("Payment", "Payment"),
        ("Account", "Account"),
        ("BillToContact", "BillToContact"),
    ],
    "InvoicePosted": [
        ("Invoice", "Invoice"),
        ("Account", "Account"),
        ("BillToContact", "BillToContact"),
    ],
    "InvoiceDue": [
        ("Invoice", "Invoice"),
        ("Account", "Account"),
        ("BillToContact", "BillToContact"),
    ],
    "CreditBalanceRefundProcessed": [
        ("Refund", "Refund"),
        ("Account", "Account"),
        ("BillToContact", "BillToContact"),
    ],
    "CreditMemoRefundProcessed": [
        ("Refund", "Refund"),
        ("Account", "Account"),
        ("BillToContact", "BillToContact"),
    ],
    "InvoicesPastDueAccountSummary": [
        ("Account", "Account"),
        ("BillToContact", "BillToContact"),
    ],
    "KeyDates": [
        ("Subscription", "Subscription"),
        ("Account", "Account"),
        ("BillToContact", "BillToContact"),
    ],
    "ManualEmailForInvoice": [
        ("Invoice", "Invoice"),
        ("Account", "Account"),
        ("BillToContact", "BillToContact"),
    ],
    "ManualEmailForPayment": [
        ("Payment", "Payment"),
        ("Account", "Account"),
        ("BillToContact", "BillToContact"),
    ],
    "PaymentRefundProcessed": [
        ("Refund", "Refund"),
        ("Payment", "Payment"),
        ("Account", "Account"),
        ("BillToContact", "BillToContact"),
    ],
    "UpcomingRenewal": [
        ("Subscription", "Subscription"),
        ("Account", "Account"),
        ("BillToContact", "BillToContact"),
    ],
    "SubscriptionCreated": [
        ("Subscription", "Subscription"),
        ("Account", "Account"),
        ("BillToContact", "BillToContact"),
    ],
    "AmendmentProcessed": [
        ("Amendment", "Amendment"),
        ("Account", "Account"),
        ("Subscription", "Subscription"),
        ("BillToContact", "BillToContact"),
    ],
}

# Run-type events produce large datasets; used for call_type inference
RUN_EVENTS = frozenset(
    {
        "BillingRunCompletion",
        "PaymentRunCompletion",
        "JournalRunCompletion",
    }
)

VALID_EVENT_NAMES: list[str] = sorted(EVENT_BASE_OBJECTS.keys())


def generate_event_parameters(
    event_name: str,
    fields: Optional[list[str]] = None,
    fields_by_object: Optional[dict[str, list[str]]] = None,
) -> list[dict[str, Any]]:
    """Build workflow.parameters.event_parameters entries for a Zuora event name.

    Returns a list with one element: {"eventName": ..., "params": [...]}.
    """
    if event_name not in EVENT_BASE_OBJECTS:
        return []

    primary_obj, primary_path = EVENT_BASE_OBJECTS[event_name]
    objects_and_paths = EVENT_PAYLOAD_OBJECTS.get(event_name, [(primary_obj, primary_path)])

    if fields_by_object and isinstance(fields_by_object, dict):
        params: list[dict[str, str]] = []
        for obj, path in objects_and_paths:
            flist = fields_by_object.get(obj)
            if isinstance(flist, list):
                for f in flist:
                    if isinstance(f, str) and f.strip():
                        params.append({"object": obj, "key": f, "value": f"<{path}.{f}>"})
    else:
        obj, path = primary_obj, primary_path
        requested = fields if fields else ["ID"]
        params = [
            {"object": obj, "key": f, "value": f"<{path}.{f}>"}
            for f in requested
            if isinstance(f, str) and f.strip()
        ]
    if not params:
        params = [{"object": primary_obj, "key": "ID", "value": f"<{primary_path}.ID>"}]
    return [{"eventName": event_name, "params": params}]


def seed_event_data_paths(event_names: list[str] | str) -> set[str]:
    """Return Data.* path strings to seed DataFlowTracker for event-triggered workflows.

    Seeds both the primary payload object and any secondary payload objects
    declared in ``EVENT_PAYLOAD_OBJECTS`` (e.g., InvoicePosted also exposes
    ``Data.Account`` and ``Data.BillToContact``).
    """
    paths: set[str] = set()
    for name in coerce_event_names_list(event_names):
        if name not in EVENT_BASE_OBJECTS:
            continue
        primary_obj, _ = EVENT_BASE_OBJECTS[name]
        paths.add(f"Data.{primary_obj}")
        paths.add(f"Data.{primary_obj}.ID")
        for obj_name in get_payload_objects(name):
            paths.add(f"Data.{obj_name}")
        ep = generate_event_parameters(name)
        for entry in ep:
            for param in entry.get("params", []):
                key = param.get("key", "")
                o = param.get("object", "")
                if o and key:
                    paths.add(f"Data.{o}.{key}")
    return paths


def get_event_reference_table() -> str:
    """Return a markdown table of all valid event names, data paths, and descriptions."""
    lines = [
        "## Valid Zuora Event Names",
        "",
        "Use these **exact** PascalCase event names — never use dotted format like "
        "`callout.X.completed`.",
        "",
        "| Event Name | Mode | Data Object | Data Path (Liquid) | Description |",
        "|---|---|---|---|---|",
    ]
    desc_map = {
        "AmendmentProcessed": "Subscription amendment processed",
        "AquaNotification": "AQuA export job completed",
        "BillingRunCompletion": "Bill run finished processing (BATCH)",
        "CreditBalanceRefundProcessed": "Credit balance refund processed",
        "CreditMemoCreated": "Credit memo created",
        "CreditMemoPosted": "Credit memo posted",
        "CreditMemoRefundProcessed": "Credit memo refund processed",
        "DataSourceOutputCompletion": "Data source export completed",
        "DebitMemoCreated": "Debit memo created",
        "DebitMemoPosted": "Debit memo posted",
        "EmailCreditMemo": "Credit memo emailed",
        "EmailDebitMemo": "Debit memo emailed",
        "GatewayReconciliation": "Payment gateway reconciliation completed",
        "InvoiceDue": "Invoice has reached its due date",
        "InvoicePosted": "Invoice posted to accounting",
        "InvoicesPastDueAccountSummary": "Account has past-due invoices",
        "JournalRunCompletion": "Journal run finished processing (BATCH)",
        "KeyDates": "Subscription key date reached",
        "ManualEmailForInvoice": "Invoice manually emailed",
        "ManualEmailForPayment": "Payment receipt manually emailed",
        "PaymentDeclined": "Payment was declined",
        "PaymentMethodClosed": "Payment method closed",
        "PaymentMethodExpiration": "Payment method expiring",
        "PaymentMethodUpdated": "Payment method updated",
        "PaymentMethodUpdaterBatchCompleted": "PMU batch completed",
        "PaymentMethodUpdaterBatchStarted": "PMU batch started",
        "PaymentProcessed": "Payment successfully processed",
        "PaymentRefundProcessed": "Payment refund processed",
        "PaymentRunCompletion": "Payment run finished processing (BATCH)",
        "SubscriptionCreated": "New subscription created",
        "TrialBalanceCompletion": "Trial balance run completed",
        "UpcomingRenewal": "Subscription renewal approaching",
    }
    for name in VALID_EVENT_NAMES:
        obj, _path = EVENT_BASE_OBJECTS[name]
        data_path = f"`Data.{obj}.ID`"
        mode = "BATCH" if name in RUN_EVENTS else "REALTIME"
        desc = desc_map.get(name, "")
        lines.append(f"| `{name}` | {mode} | {obj} | {data_path} | {desc} |")
    lines.append("")
    return "\n".join(lines)


def suggest_event_name(raw_name: str) -> Optional[str]:
    """Given an invalid/fuzzy event name, suggest the closest valid one."""
    if raw_name in EVENT_BASE_OBJECTS:
        return raw_name

    lower = raw_name.lower().replace(".", "").replace("_", "").replace("-", "").replace(" ", "")
    for valid in VALID_EVENT_NAMES:
        if valid.lower() == lower:
            return valid

    for valid in VALID_EVENT_NAMES:
        if lower in valid.lower():
            return valid

    # Match dotted format: "callout.BillRun.completed" → search by object + action
    dotted = re.match(r"(?:callout\.)?(\w+?)\.(\w+)", raw_name, re.IGNORECASE)
    if dotted:
        obj_part = dotted.group(1).lower()
        action_part = dotted.group(2).lower()
        # Map common action words to event suffixes
        action_synonyms = {
            "completed": "completion",
            "complete": "completion",
            "finished": "completion",
            "done": "completion",
            "posted": "posted",
            "processed": "processed",
            "declined": "declined",
            "created": "created",
            "due": "due",
            "closed": "closed",
            "updated": "updated",
            "expiration": "expiration",
            "expired": "expiration",
            "expiring": "expiration",
        }
        mapped_action = action_synonyms.get(action_part, action_part)
        # Try matching both the raw object name and known aliases
        for valid in VALID_EVENT_NAMES:
            vl = valid.lower()
            _, payload_path = EVENT_BASE_OBJECTS[valid]
            if (obj_part in vl or obj_part == payload_path.lower()) and mapped_action in vl:
                return valid

    return None


def is_run_event(event_name: str) -> bool:
    """True if this event is a run-type event producing large datasets."""
    return event_name in RUN_EVENTS


def is_multi_object_event(event_name: str) -> bool:
    """True if this event exposes multiple payload objects beyond the primary one.

    Multi-object events expose related objects in their Data.* payload, e.g.
    PaymentProcessed exposes Payment, Account, and BillToContact. Single-object
    events expose only their primary object (e.g. BillingRunCompletion → BillingRun).
    """
    payload_objects = EVENT_PAYLOAD_OBJECTS.get(event_name)
    if not payload_objects:
        return False
    return len(payload_objects) > 1


def get_payload_objects(event_name: str) -> list[str]:
    """Return the list of payload object names exposed by an event's Data.* payload.

    For single-object events this returns a single-element list with the primary object.
    For multi-object events this returns all payload objects (e.g. Payment, Account,
    BillToContact for PaymentProcessed).
    """
    if event_name not in EVENT_BASE_OBJECTS:
        return []
    primary_obj, primary_path = EVENT_BASE_OBJECTS[event_name]
    payload = EVENT_PAYLOAD_OBJECTS.get(event_name)
    if not payload:
        return [primary_obj]
    return [obj for obj, _ in payload]
