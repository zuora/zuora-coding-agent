"""Reference lookup module for Zuora workflow building blocks.

Renders ground-truth reference data in a form the LLM agent can consume as
tool output. Topics covered:

* ``events`` — Zuora workflow event names, payload objects, and Data.* paths.
* ``task_types`` — catalog of task ``action_type``s with purpose summaries.
* ``task`` — deep detail for a single task (required + all parameters,
  linkage types).
* ``linkage_rules`` — linkage types valid from each source task.
* ``planning_guidance`` — named reference patterns (run_event, iterate,
  email, callout, ...).
* ``liquid_custom_filters`` — Zuora-added Liquid filter reference (no subtopic).

Task metadata is sourced from the generated Pydantic models
(``TASK_TYPE_CONFIG_MAP`` and ``TASK_TYPE_TASK_MAP``); field descriptions
come from the datamodel-code-generator emitted PEP-257 docstrings, which are
parsed once at import time by ``_build_field_docs``.

Object metadata (fields, flags, relationships, cardinality) is served by
``lookup_zuora_schema`` / ``list_zuora_objects`` which prefer the live
``/v1/describe`` endpoint.  The legacy ``object_fields`` and
``object_relationships`` topics are kept for backward compatibility but
now return a redirect message pointing the caller to those tools.

All responses follow the shape::

    {"topic": str, "subtopic": str|None, "content": str (markdown), "data": dict}
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Optional

from workflow_engine.workflow_reference.event_parameters import (
    EVENT_BASE_OBJECTS,
    EVENT_PAYLOAD_OBJECTS,
    RUN_EVENTS,
    VALID_EVENT_NAMES,
    generate_event_parameters,
    is_run_event,
)
from workflow_engine.workflow_reference.liquid_custom_filters import (
    LIQUID_CUSTOM_FILTERS_REFERENCE,
)
from workflow_engine.workflow_reference.models import (
    TASK_LINKAGE_TYPES,
    TASK_TYPE_CONFIG_MAP,
    TASK_TYPE_TASK_MAP,
    TaskTypeEnum,
)
from workflow_engine.workflow_reference.planning_guidance import TASK_TYPE_GUIDANCE

# ---------------------------------------------------------------------------
# Reference data loaded once at import
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent
_GENERATED_PATH = _HERE / "models" / "generated.py"

_KB_DIR = _HERE.parent.parent / "knowledge_base"
_RELATIONS_MD = _KB_DIR / "zuora_objects_relationships.md"


# ---------------------------------------------------------------------------
# Field docstring extraction (datamodel-code-generator emits PEP-257-style
# triple-quoted strings after each annotated field, which Pydantic does NOT
# surface via ``Field.description``). We parse them once via AST so downstream
# renderers can show rich parameter documentation without a separate manifest.
# ---------------------------------------------------------------------------

_FIELD_DOCS: dict[tuple[str, str], str] = {}


def _build_field_docs() -> None:
    """Populate ``_FIELD_DOCS`` with ``{(class_name, field_name): docstring}``."""
    if _FIELD_DOCS or not _GENERATED_PATH.exists():
        return
    tree = ast.parse(_GENERATED_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        body = node.body
        for i, stmt in enumerate(body):
            if not (isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)):
                continue
            fname = stmt.target.id
            if i + 1 >= len(body):
                continue
            nxt = body[i + 1]
            if (
                isinstance(nxt, ast.Expr)
                and isinstance(nxt.value, ast.Constant)
                and isinstance(nxt.value.value, str)
            ):
                _FIELD_DOCS[(node.name, fname)] = nxt.value.value.strip()


_build_field_docs()


def _field_description(cls: type, field_name: str) -> str:
    """Return the PEP-257 docstring for a Pydantic field, walking the MRO."""
    for base in cls.__mro__:
        key = (base.__name__, field_name)
        if key in _FIELD_DOCS:
            return _FIELD_DOCS[key]
    return ""


# Planning guidance patterns — inline so they load fast and stay in sync with
# the system prompt. These are the authoritative reference; the system prompt
# should cite/summarize from here rather than duplicate them.
_PLANNING_GUIDANCE: dict[str, dict[str, Any]] = {
    "run_event": {
        "title": "Triggering on a run-completion event",
        "when": (
            "You want the workflow to process records created by a specific run "
            "(BillingRunCompletion, PaymentRunCompletion, JournalRunCompletion)."
        ),
        "steps": [
            "Set trigger.type='event' and include the run event in event_names.",
            "Set call_type='BATCH' (run events produce large datasets).",
            "First task MUST be an Export (NOT Query) against the run's output object. "
            "Runs typically produce >2000 records, which would make Query fail. Filter "
            "with where_clause = \"<Object>.SourceId = '{{Data.<RunObject>.ID}}'\" "
            "(e.g. \"Invoice.SourceId = '{{Data.BillingRun.ID}}'\" for BillingRunCompletion). "
            "Use Data::Link instead only if you need a SQL JOIN across multiple objects.",
            "Pull every 1:1 / N:1 related object on the same Export via ZOQL field paths "
            '(e.g. add "Account" and "BillToContact" to fields so Data.Account.* and '
            "Data.BillToContact.* are populated inside the loop — no inner Query needed).",
            "Add an Iterate over the Export; per-record tasks link with edge_type 'For Each'.",
            "Inside the loop, use Query ONLY for 1:N child objects (e.g. Query InvoiceItem "
            "WHERE InvoiceId = '{{Data.Invoice.Id}}') — per-parent child count is typically <2000.",
            "Downstream tasks reference per-record fields via Data.<ObjectName>.*",
        ],
        "example": (
            "BillingRunCompletion → Export Invoice WHERE Invoice.SourceId='{{Data.BillingRun.ID}}' "
            "(with Account + BillToContact fields joined) → Iterate → Query InvoiceItem "
            "(by InvoiceId) → Email / Callout."
        ),
    },
    "realtime_event": {
        "title": "Triggering on a per-record event",
        "when": (
            "You want the workflow to fire once per record (InvoicePosted, "
            "PaymentProcessed, SubscriptionCreated, ...)."
        ),
        "steps": [
            "Set trigger.type='event' and include the single event name.",
            "Set call_type='REALTIME' (NOT BATCH — BATCH is only for run-completion events).",
            "The trigger payload is available as Data.<Object>.* (plus any extra "
            "payload objects; see lookup_workflow_reference(topic='events', "
            "subtopic='<EventName>') for that event's full Data.* paths).",
            "If the event payload has everything you need (e.g. Data.BillToContact.WorkEmail "
            "for an InvoicePosted → Email flow), skip straight to the action task — "
            "no Export/Iterate needed.",
            "If you need additional fields not in the event payload, use Query (NOT Export) — "
            "one record by ID is guaranteed <2000 and Query works in REALTIME/UIACTION. "
            "Example: Query Account by event Data.Invoice.AccountId to fetch Account-level "
            "fields before the action.",
        ],
        "example": (
            "InvoicePosted → Email {{Data.BillToContact.WorkEmail}} "
            "(all fields come from the event payload — no extra fetch).\n"
            "SubscriptionCreated → Query Subscription (by event Data.Subscription.Id) "
            "→ Callout to provisioning system."
        ),
    },
    "iterate": {
        "title": "Iterating over a collection",
        "when": "You need to run a sub-flow for each row in a Query/Export/GraphQuery result.",
        "steps": [
            "Add a Query/Export/GraphQuery/Data::Aqua task that produces the collection.",
            "Add an Iterate task whose `object` points to that predecessor: "
            "file-producing predecessors (Export, Data::Aqua, Data::Link) need a "
            "filename ending in .csv or .csv.zip; Query/GraphQuery use the Data.* array.",
            "Link predecessor --Success--> Iterate.",
            "Per-record children link from Iterate with type 'For Each'.",
            "After-loop children link from Iterate with type 'Complete'.",
            "Inside the loop, reference row fields as Data.<ObjectName>.<Field>.",
        ],
        "example": (
            "Export Invoice → Iterate 'Export_Invoice.csv' --For Each--> Email (per invoice)."
        ),
    },
    "email": {
        "title": "Sending an Email",
        "when": "A recipient exists (Data.BillToContact.WorkEmail, Account.* contact, or a literal).",
        "steps": [
            "Ensure the recipient email is in scope (event payload or preceding Query).",
            "Put a BRIEF in parameters.email — NOT the full HTML template. Required "
            "brief keys: to[] (Liquid recipient expressions), from (verified sender), "
            "subject (specific + customer-ready — never 'Notification'), intent "
            "(one-sentence purpose), data_vars (prioritized Liquid expressions the body "
            "must surface). Optional: tone (professional/friendly/urgent), cta "
            "({label, href}).",
            "The creative sub-agent renders the HTML template from the brief at build "
            "time — do NOT write the template yourself unless the user supplies "
            "pre-approved copy.",
            "For dynamic content, use Liquid Data.* paths in subject and data_vars.",
        ],
        "example": (
            "{email: {to: ['{{Data.BillToContact.WorkEmail}}'], from: 'billing@zuora.com', "
            "subject: 'Payment reminder — Invoice #{{Data.Invoice.InvoiceNumber}}', "
            "intent: 'Remind the bill-to contact an invoice is due within 3 days.', "
            "data_vars: ['{{Data.BillToContact.FirstName}}', "
            "'{{Data.Invoice.InvoiceNumber}}', '{{Data.Invoice.Amount | money}}', "
            "'{{Data.Invoice.DueDate}}'], tone: 'friendly', cta: {label: 'Pay Now', "
            "href: '{{Data.Invoice.URL}}'}}}"
        ),
    },
    "callout": {
        "title": "Making a Callout (Zuora API fallback or external system)",
        "when": (
            "Two scenarios: (1) ZUORA API FALLBACK — invoke a Zuora REST endpoint "
            "that has no dedicated task type (e.g. POST /v1/bill-runs/{id}/post, "
            "POST /v1/invoices/{id}/email, POST /v1/orders). (2) EXTERNAL SYSTEM "
            "INTEGRATION — webhook / SaaS / partner / internal system."
        ),
        "steps": [
            "Use action_type='Callout' (synchronous) or 'AsynchronousCallout' (fire-and-forget).",
            "Set parameters.url and method (GET / POST / PUT / PATCH / DELETE). "
            "Parameters sit directly on `parameters` (no `callout` sub-object).",
            "headers default to [{key:'Content-Type', value:'application/json'}]; override "
            "only when needed. authorization: {type:'none'} (dict, NOT a string).",
            "AT PLAN TIME — keep it minimal for mutating methods: set body_brief "
            "(one-sentence description) + body_vars (list of Liquid expressions the body "
            "must include). Do NOT write raw_body yet.",
            "AFTER PLAN APPROVAL, BEFORE build_workflow_definition — expand every brief "
            "into a real raw_body. For Zuora API URLs call "
            "lookup_zuora_api_spec(method=..., path=...) to ground every field name in "
            "the spec; for external systems infer a minimal payload from the user's intent "
            "and surface the schema as an assumption.",
            "Use Liquid in raw_body: {{Data.X.Y}} (quote strings; leave numbers/booleans "
            "unquoted), {% for %} for arrays (with `{% unless forloop.last %},{% endunless %}`), "
            "{% if %} for optional fields, filters (money, date, downcase).",
            "Every {{Data.X.Y}} must come from the event or a preceding task — walk "
            "data_payload_trace to confirm before building.",
            "Add retry_rules for idempotent calls: {retry_count, retry_window, retry_factor}.",
        ],
        "example": (
            "Plan-time brief: {url: 'https://tax.example.com/v1/calc', method: 'POST', "
            "body_brief: 'Send invoice header + line items for tax calculation.', "
            "body_vars: ['{{Data.Invoice.Id}}', '{{Data.Invoice.Amount}}', "
            "'{{Data.Invoice.InvoiceItems[*].ChargeAmount}}']}.\n\n"
            "Post-approval (raw_body authored before build): {url: '...', method: 'POST', "
            'raw_body: \'{"invoice_id": "{{Data.Invoice.Id}}", "line_items": [{% for '
            'item in Data.Invoice.InvoiceItems %}{"id": "{{item.Id}}", "amount": '
            "{{item.ChargeAmount}}}{% unless forloop.last %},{% endunless %}{% endfor %}]}'}."
        ),
    },
    "parent_child_filter": {
        "title": "Filtering a child object by its parent",
        "when": (
            "You have a parent object in scope (Invoice, Account, ...) and want to "
            "list its children (InvoiceItem, Contact, Subscription, ...)."
        ),
        "steps": [
            "Call lookup_zuora_schema(object_name='<Child>', include_relationships=True) "
            "to find the canonical FK field name and the cardinality (TO_ONE/TO_MANY).",
            "In the child Query/Export, add a where_clause: <FK> = '{{Data.<Parent>.Id}}'.",
            "Query (ZOQL) expects bare field names: InvoiceId, not InvoiceItem.InvoiceId.",
            "Export uses <Object>.<Field> prefixing; InvoiceItem.InvoiceId is correct for Export.",
        ],
        "example": "Query InvoiceItem WHERE InvoiceId = '{{Data.Invoice.Id}}'",
    },
}


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


def lookup(topic: str, subtopic: Optional[str] = None) -> dict[str, Any]:
    """Return reference data for a topic.

    Args:
        topic: One of 'events', 'task_types', 'task', 'linkage_rules',
            'planning_guidance', 'liquid_custom_filters', 'data_retrieval',
            'error_taxonomy'.
        subtopic: Drill-down selector (event name, task action_type,
            planning pattern key). Required for 'task' and 'planning_guidance'.
            Ignored for 'liquid_custom_filters', 'data_retrieval', 'error_taxonomy'.

    The legacy topics ``object_fields`` and ``object_relationships`` remain
    supported but now return a redirect message pointing the caller to
    ``lookup_zuora_schema`` (live ``/describe`` data).
    """
    topic_norm = (topic or "").lower().strip()

    if topic_norm == "events":
        return _lookup_events(subtopic)
    if topic_norm == "task_types":
        return _lookup_task_types()
    if topic_norm == "task":
        return _lookup_task(subtopic)
    if topic_norm == "linkage_rules":
        return _lookup_linkage_rules(subtopic)
    if topic_norm in ("object_fields", "object_relationships"):
        return _redirect_to_lookup_zuora_schema(topic_norm, subtopic)
    if topic_norm == "planning_guidance":
        return _lookup_planning_guidance(subtopic)
    if topic_norm == "data_retrieval":
        return _lookup_data_retrieval()
    if topic_norm == "error_taxonomy":
        return _lookup_error_taxonomy()
    if topic_norm == "liquid_custom_filters":
        return _lookup_liquid_custom_filters()

    return {
        "topic": topic,
        "subtopic": subtopic,
        "content": (
            f"Unknown topic {topic!r}. Valid topics: events, task_types, task, "
            "linkage_rules, planning_guidance, liquid_custom_filters, "
            "data_retrieval, error_taxonomy. "
            "For object fields or relationships, use `lookup_zuora_schema`."
        ),
        "data": {},
    }


def _redirect_to_lookup_zuora_schema(
    topic: str,
    subtopic: Optional[str],
) -> dict[str, Any]:
    """Legacy shim: redirect object-schema callers to ``lookup_zuora_schema``."""
    example_call = (
        f"lookup_zuora_schema(object_name={subtopic!r}, include_relationships=True)"
        if subtopic
        else "lookup_zuora_schema(object_name='<Object>', include_relationships=True)"
    )
    content = (
        f"## Use `lookup_zuora_schema` for `{topic}`\n\n"
        "Object fields, per-field flags (selectable / updateable / filterable / "
        "custom / type / picklist options / contexts), and relationship "
        "cardinality are served by the live `/v1/describe` endpoint via "
        "`lookup_zuora_schema` (with `list_zuora_objects` for the catalog).\n\n"
        f"Call instead: `{example_call}`\n\n"
        "- Use `context_filter='export'` to restrict to Export-safe fields.\n"
        "- Use `include_relationships=True` to get parent/child cardinality."
    )
    return {
        "topic": topic,
        "subtopic": subtopic,
        "content": content,
        "data": {
            "redirect_to": "lookup_zuora_schema",
            "suggested_call": example_call,
        },
    }


# ---------------------------------------------------------------------------
# Topic: events
# ---------------------------------------------------------------------------


def _lookup_events(subtopic: Optional[str]) -> dict[str, Any]:
    if not subtopic:
        run_events = sorted(RUN_EVENTS)
        realtime = sorted(set(VALID_EVENT_NAMES) - RUN_EVENTS)
        lines = [
            "## Zuora Workflow Events",
            "",
            "### Run (batch) events",
            "These emit after a run completes. Use `call_type='BATCH'` and "
            "filter child records by `SourceId = '{{Data.<RunObject>.ID}}'`.",
            "",
            *[f"- `{n}` → Data.{EVENT_BASE_OBJECTS[n][0]}" for n in run_events],
            "",
            "### Realtime (per-record) events",
            "Use `call_type='REALTIME'`.",
            "",
            *[f"- `{n}` → Data.{EVENT_BASE_OBJECTS[n][0]}" for n in realtime],
            "",
            "For a specific event's payload, call "
            "`lookup_workflow_reference(topic='events', subtopic='<EventName>')`.",
        ]
        return {
            "topic": "events",
            "subtopic": None,
            "content": "\n".join(lines),
            "data": {"run_events": run_events, "realtime_events": realtime},
        }

    if subtopic not in EVENT_BASE_OBJECTS:
        return {
            "topic": "events",
            "subtopic": subtopic,
            "content": f"Unknown event `{subtopic}`. See `lookup(topic='events')`.",
            "data": {},
        }

    primary_obj, _primary_path = EVENT_BASE_OBJECTS[subtopic]
    payload_objects = EVENT_PAYLOAD_OBJECTS.get(subtopic, [(primary_obj, primary_obj)])
    ep = generate_event_parameters(subtopic)

    data_paths: list[str] = []
    for entry in ep:
        for p in entry.get("params", []):
            obj = p.get("object") or entry.get("object") or primary_obj
            data_paths.append(f"Data.{obj}.{p['key']}")

    lines = [
        f"## Event: `{subtopic}`",
        "",
        f"- **Primary object:** `{primary_obj}`",
        f"- **Category:** {'Run (batch)' if is_run_event(subtopic) else 'Realtime'}",
        f"- **Recommended call_type:** " f"`{'BATCH' if is_run_event(subtopic) else 'REALTIME'}`",
        "",
        "### Payload objects",
        "",
        *[f"- `{obj}` — path `Data.{obj}.*`" for obj, _ in payload_objects],
        "",
        "### Data.* paths seeded for Liquid",
        "",
    ]
    if data_paths:
        lines += [f"- `{p}`" for p in data_paths[:40]]
    else:
        lines.append("- _(none)_")
    lines.append("")
    if is_run_event(subtopic):
        lines += [
            "### Run event note",
            "",
            "Objects created by this run carry a `SourceId` field referencing the "
            f"run id. Use it in your Export/Query where-clause, e.g. "
            f"`Invoice.SourceId = '{{{{Data.{primary_obj}.ID}}}}'`.",
        ]

    return {
        "topic": "events",
        "subtopic": subtopic,
        "content": "\n".join(lines),
        "data": {
            "primary_object": primary_obj,
            "payload_objects": [obj for obj, _ in payload_objects],
            "run_event": is_run_event(subtopic),
            "recommended_call_type": "BATCH" if is_run_event(subtopic) else "REALTIME",
            "data_paths": data_paths,
            "event_parameters": ep,
        },
    }


# ---------------------------------------------------------------------------
# Topic: task_types
# ---------------------------------------------------------------------------


def _task_purpose(action_type: str) -> str:
    """Return the first line of the ``*Task`` class docstring (from the schema description)."""
    cls = TASK_TYPE_TASK_MAP.get(action_type)
    if cls is None:
        return ""
    doc = (cls.__doc__ or "").strip()
    if not doc:
        return ""
    return doc.split("\n", 1)[0].strip()


def _group_action_type(action: str) -> str:
    """Categorize an ``action_type`` for the task catalog rendering."""
    if action in {
        "Query",
        "Export",
        "GraphQuery",
        "Data::Aqua",
        "Data::Link",
        "Data::BillingPreviewRun",
        "Data::Warehouse",
    }:
        return "Data"
    if action.startswith("Logic::") or action in ("If", "Iterate", "Delay", "Approval"):
        return "Logic"
    if action in ("Create", "Update", "Delete") or action.startswith("CustomObject::"):
        return "CRUD"
    if action in ("Email", "Notifications::SMS", "Notifications::Kafka"):
        return "Notification"
    if action in (
        "Callout",
        "AsynchronousCallout",
        "Execute::WorkflowTask",
        "Script::JavaScript",
    ):
        return "External"
    if action.startswith("Billing::") or action in ("InvoiceGenerate", "WriteOff"):
        return "Billing"
    if action.startswith("Payment::"):
        return "Payment"
    if action.startswith(("File::", "Upload::", "Download::")) or action == "Attachment":
        return "File"
    if action.startswith("UsageMediation::") or action in (
        "Mediation::SendEvents",
        "Usage::ImportUsage",
    ):
        return "Usage Mediation"
    if action.startswith("UI::"):
        return "UI"
    if action.startswith("Reporting::"):
        return "Reporting"
    return "Other"


def _lookup_task_types() -> dict[str, Any]:
    groups: dict[str, list[tuple[str, str]]] = {
        "Data": [],
        "Logic": [],
        "CRUD": [],
        "Notification": [],
        "External": [],
        "Billing": [],
        "Payment": [],
        "File": [],
        "Usage Mediation": [],
        "UI": [],
        "Reporting": [],
        "Other": [],
    }
    for member in TaskTypeEnum:
        action = member.value
        groups[_group_action_type(action)].append((action, _task_purpose(action)))

    lines = ["## Zuora Workflow Task Catalog", ""]
    for grp, items in groups.items():
        if not items:
            continue
        lines.append(f"### {grp}")
        lines.append("")
        for action, purpose in sorted(items):
            purpose_snippet = purpose[:120] if purpose else ""
            lines.append(
                f"- `{action}` — {purpose_snippet}" if purpose_snippet else f"- `{action}`"
            )
        lines.append("")

    return {
        "topic": "task_types",
        "subtopic": None,
        "content": "\n".join(lines),
        "data": {"groups": {g: [a for a, _ in items] for g, items in groups.items() if items}},
    }


# ---------------------------------------------------------------------------
# Topic: task (deep detail for one action_type)
# ---------------------------------------------------------------------------


_COMMON_FIELDS: frozenset[str] = frozenset(
    {
        "strict_variables",
        "disable_validation",
        "delete_payload_paths",
    }
)


def _render_default(default: Any) -> Optional[str]:
    """Format a Pydantic default for display (``None``/empty returns ``None``)."""
    if default is None:
        return None
    if isinstance(default, bool):
        return "true" if default else "false"
    if default == "" or default == [] or default == {}:
        return None
    if isinstance(default, (list, dict)):
        return str(default)
    return str(default)


def _resolve_default(cls: type, field_name: str) -> Any:
    """Return the Pydantic model default (calling ``default_factory`` if set)."""
    field = cls.model_fields.get(field_name)  # type: ignore[attr-defined]
    if field is None:
        return None
    default = getattr(field, "default", None)
    if default is not None:
        return default
    factory = getattr(field, "default_factory", None)
    if factory is not None:
        try:
            return factory()
        except Exception:
            return None
    return None


def _lookup_task(subtopic: Optional[str]) -> dict[str, Any]:
    if not subtopic:
        return {
            "topic": "task",
            "subtopic": None,
            "content": (
                "Please provide a task action_type as subtopic, e.g. "
                "`lookup(topic='task', subtopic='Query')`. For the full catalog, "
                "use `lookup(topic='task_types')`."
            ),
            "data": {},
        }

    task_cls = TASK_TYPE_TASK_MAP.get(subtopic)
    config_cls = TASK_TYPE_CONFIG_MAP.get(subtopic)
    if task_cls is None or config_cls is None:
        return {
            "topic": "task",
            "subtopic": subtopic,
            "content": (
                f"Unknown task action_type `{subtopic}`. See " "`lookup(topic='task_types')`."
            ),
            "data": {},
        }

    purpose = (task_cls.__doc__ or "").strip()

    required: list[dict[str, str]] = []
    for top_field in ("object", "object_id"):
        fld = task_cls.model_fields.get(top_field)
        if fld is not None and fld.is_required():
            required.append(
                {
                    "path": top_field,
                    "level": "task",
                    "description": _field_description(task_cls, top_field)
                    .split("\n", 1)[0]
                    .strip(),
                }
            )

    optional_params: list[str] = []
    for pname, field in config_cls.model_fields.items():
        if pname in _COMMON_FIELDS:
            continue
        if field.is_required():
            required.append(
                {
                    "path": f"parameters.{pname}",
                    "level": "parameters",
                    "description": _field_description(config_cls, pname).split("\n", 1)[0].strip(),
                }
            )
        else:
            optional_params.append(pname)

    lines = [
        f"## Task: `{subtopic}`",
        "",
        f"**Purpose:** {purpose}" if purpose else "",
        "",
        "### Required fields",
        "",
    ]
    if required:
        for entry in required:
            suffix = " (task-level)" if entry["level"] == "task" else " (in `parameters`)"
            desc = entry["description"]
            line = f"- `{entry['path']}`{suffix}"
            if desc:
                line += f" — {desc}"
            lines.append(line)
    else:
        lines.append("_(none beyond id/name/action_type)_")

    lines += ["", "### Optional parameters", ""]
    for p in optional_params:
        desc = _field_description(config_cls, p).split("\n", 1)[0].strip()
        default_display = _render_default(_resolve_default(config_cls, p))
        suffix = f" (default: `{default_display}`)" if default_display else ""
        lines.append(f"- `{p}`{suffix}" + (f" — {desc}" if desc else ""))

    linkages = TASK_LINKAGE_TYPES.get(subtopic)
    lines += ["", "### Valid outgoing linkage types", ""]
    if linkages is None:
        lines.append("_(dynamic — e.g., `Case_1`, `Case_2`, `Case_Else` for Logic::Case)_")
    else:
        lines.append(", ".join(f"`{t}`" for t in linkages))

    behavioral = TASK_TYPE_GUIDANCE.get(subtopic, "").strip()
    if behavioral:
        lines += ["", "### Behavioral guidance", "", behavioral]

    return {
        "topic": "task",
        "subtopic": subtopic,
        "content": "\n".join(lines),
        "data": {
            "purpose": purpose,
            "required": required,
            "optional_parameters": optional_params,
            "linkage_types": list(linkages) if linkages else None,
            "behavioral_guidance": behavioral or None,
        },
    }


# ---------------------------------------------------------------------------
# Topic: linkage_rules
# ---------------------------------------------------------------------------


def _lookup_linkage_rules(subtopic: Optional[str]) -> dict[str, Any]:
    VALID_LINKAGES = TASK_LINKAGE_TYPES  # noqa: N806

    if not subtopic:
        lines = [
            "## Linkage Rules",
            "",
            "Each task type emits specific linkage types that target downstream "
            "tasks. Use these when wiring `linkages`.",
            "",
            "| Source task | Valid linkage types |",
            "|---|---|",
        ]
        for action in sorted(VALID_LINKAGES.keys()):
            types = VALID_LINKAGES[action]
            if types is None:
                desc = "_dynamic (Case_1..Case_N, Case_Else)_"
            else:
                desc = ", ".join(f"`{t}`" for t in types)
            lines.append(f"| `{action}` | {desc} |")
        return {
            "topic": "linkage_rules",
            "subtopic": None,
            "content": "\n".join(lines),
            "data": {k: v for k, v in VALID_LINKAGES.items()},
        }

    types = VALID_LINKAGES.get(subtopic)
    if types is None and subtopic not in VALID_LINKAGES:
        return {
            "topic": "linkage_rules",
            "subtopic": subtopic,
            "content": f"Unknown task action_type `{subtopic}`.",
            "data": {},
        }
    if types is None:
        content = (
            f"### `{subtopic}` linkage rules\n\n"
            f"`{subtopic}` emits **dynamic** linkage types: `Case_1`, `Case_2`, ... "
            "`Case_N`, plus `Case_Else` for the default branch."
        )
    else:
        content = f"### `{subtopic}` linkage rules\n\n" + ", ".join(f"`{t}`" for t in types)
    return {
        "topic": "linkage_rules",
        "subtopic": subtopic,
        "content": content,
        "data": {"linkage_types": types},
    }


# ---------------------------------------------------------------------------
# Relationship helper (retained for plan_validator until resolver migration)
# ---------------------------------------------------------------------------


_RELATIONS_CACHE: dict[str, dict[str, list[dict[str, str]]]] = {}


def load_object_relationships() -> dict[str, dict[str, list[dict[str, str]]]]:
    """Parse ``zuora_objects_relationships.md`` for legacy callers.

    Returns ``{object_name: {"references": [...], "referenced_by": [...]}}``.
    Prefer :func:`tools.workflow_reference.object_metadata.get_object_metadata`
    for new code - this helper only exists to keep the plan validator
    running until it is migrated to the runtime-first resolver.
    """
    if _RELATIONS_CACHE:
        return _RELATIONS_CACHE
    if not _RELATIONS_MD.exists():
        return {}
    current_obj: Optional[str] = None
    section: Optional[str] = None
    entry: dict[str, dict[str, list[dict[str, str]]]] = {}

    for raw_line in _RELATIONS_MD.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("## ") and len(line) > 3:
            current_obj = line[3:].strip()
            entry[current_obj] = {"references": [], "referenced_by": []}
            section = None
            continue
        if line.startswith("**References"):
            section = "references"
            continue
        if line.startswith("**Referenced"):
            section = "referenced_by"
            continue
        if not current_obj or not section or not line.startswith("- "):
            continue
        body = line[2:].strip()
        if section == "references":
            m = re.match(r"([A-Za-z][\w]*)\s*->\s*([A-Za-z][\w]*)\s*(.*)$", body)
            if m:
                entry[current_obj]["references"].append(
                    {
                        "field": m.group(1),
                        "target_object": m.group(2),
                        "raw_label": body,
                    }
                )
        elif section == "referenced_by":
            m = re.match(r"([A-Za-z][\w]*)\.([A-Za-z][\w]*)", body)
            if m:
                entry[current_obj]["referenced_by"].append(
                    {
                        "source_object": m.group(1),
                        "field": m.group(2),
                    }
                )
    _RELATIONS_CACHE.update(entry)
    return _RELATIONS_CACHE


# ---------------------------------------------------------------------------
# Topic: planning_guidance
# ---------------------------------------------------------------------------


def _lookup_planning_guidance(subtopic: Optional[str]) -> dict[str, Any]:
    if not subtopic:
        lines = [
            "## Planning guidance patterns",
            "",
            "Call `lookup(topic='planning_guidance', subtopic='<pattern>')` to "
            "see step-by-step guidance. Patterns:",
            "",
        ]
        for key, g in _PLANNING_GUIDANCE.items():
            lines.append(f"- `{key}` — {g['title']}")
        return {
            "topic": "planning_guidance",
            "subtopic": None,
            "content": "\n".join(lines),
            "data": {"patterns": list(_PLANNING_GUIDANCE.keys())},
        }

    g = _PLANNING_GUIDANCE.get(subtopic)  # type: ignore[assignment]
    if not g:
        return {
            "topic": "planning_guidance",
            "subtopic": subtopic,
            "content": (
                f"Unknown pattern `{subtopic}`. "
                "See `lookup(topic='planning_guidance')` for the list."
            ),
            "data": {},
        }

    lines = [
        f"## {g['title']}",
        "",
        f"**When to use:** {g['when']}",
        "",
        "### Steps",
        "",
    ]
    lines += [f"{i+1}. {step}" for i, step in enumerate(g["steps"])]
    lines += ["", "### Example", "", g["example"]]
    return {
        "topic": "planning_guidance",
        "subtopic": subtopic,
        "content": "\n".join(lines),
        "data": g,
    }


# ---------------------------------------------------------------------------
# Topic: liquid_custom_filters (Zuora-added Liquid::Filters)
# ---------------------------------------------------------------------------


def _lookup_liquid_custom_filters() -> dict[str, Any]:
    return {
        "topic": "liquid_custom_filters",
        "subtopic": None,
        "content": LIQUID_CUSTOM_FILTERS_REFERENCE.strip(),
        "data": {"kind": "liquid_custom_filters_reference"},
    }


# ---------------------------------------------------------------------------
# Topic: data_retrieval (Query vs Export vs Data::Link vs GraphQuery ...)
# ---------------------------------------------------------------------------


_DATA_RETRIEVAL_CONTENT = """## Data Retrieval Decision Matrix

Choose the right data-fetching task based on the use-case pattern, not
just record count.

| Use Case Pattern | Task Type | Notes |
|---|---|---|
| **SPECIFIC RECORD**: "Get invoice by ID", "fetch account {id}" | `Query` | Only when you have the exact ID and count < 2000. Safe in REALTIME / UIACTION workflows. |
| **PER-RECORD CHILD LOOKUP**: Inside `Iterate`, fetch children by parent FK | `Query` | `InvoiceItem WHERE InvoiceId = '{{Data.Invoice.Id}}'` etc. — child-per-parent count is typically well under the 2000 limit. |
| **POLLING / UNKNOWN VOLUME**: "Get all X", "fetch recent X", "check for new X" | `Export` | Supports ORDER BY and relative dates (`today - 30`). |
| **RUN RESULTS**: Bill run / payment run / journal run completion | `Export` (or `Data::Link` if JOIN needed) | Runs produce large datasets — **NEVER `Query`**. Filter via `SourceId = '{{Data.<RunObject>.ID}}'`. |
| **REPORTING / ANALYTICS**: Any aggregation (GROUP BY, COUNT, SUM, AVG) | `Export` | `Query` does not support GROUP BY / HAVING. |
| **SORTED RESULTS**: Need ORDER BY | `Export` | `Query` has no ORDER BY. |
| **TIME-BASED**: "Last 30 days", "since yesterday" | `Export` | Supports relative dates. |
| **MULTI-OBJECT JOIN**: "Invoices with line items (flat)", "payments with accounts" | `Data::Link` | Full SQL JOIN support (INNER / LEFT / RIGHT). |
| **NESTED HIERARCHY**: "Account with subscriptions and rate plans" (single record) | `GraphQuery` | Returns nested structure in one call; max 200 per collection. |
| **CUSTOM OBJECT** | `CustomObject::Query` | Custom objects are not in ZOQL / Data::Link. |
| **BILLING PREVIEW** | `Data::BillingPreviewRun` | Dedicated preview endpoint. |
| **WAREHOUSE ANALYTICS** | `Data::Warehouse` | Data Warehouse SQL connector. |

### Call-type rules (event-triggered workflows)

- **BATCH** — only for run-completion events (`BillingRunCompletion`,
  `PaymentRunCompletion`, `JournalRunCompletion`). Use `Export` → `Iterate`
  patterns.
- **REALTIME** — all other events (`InvoicePosted`, `PaymentProcessed`,
  `PaymentDeclined`, `SubscriptionCreated`, `CreditMemoPosted`,
  `UpcomingRenewal`, ...). One record per event firing. Use `Query` for
  data retrieval when you need additional fields.

### Parent + Children pattern (Export → Iterate → Query)

When you need parent records with their child records, do **not** use a
single `Data::Link` JOIN — it multiplies rows. Instead:

1. `Export` the parent objects, pulling every 1:1 / N:1 related field on
   the same Export (see "Join on the upstream task").
2. `Iterate` over each parent record.
3. `Query` only the 1:N child objects inside the loop, filtering by the
   parent's ID (e.g. `InvoiceItem WHERE InvoiceId = '{{Data.Invoice.Id}}'`).
4. Action task (`Callout`, `Email`, `Create`, etc.) with both parent and
   child data available.

### Join on the upstream task (CRITICAL)

`Export` supports ZOQL field paths that traverse
foreign-key relationships (`Invoice.Account.Name`,
`Invoice.Account.BillToContact.WorkEmail`, ...). Use this to pull every
1:1 / N:1 related object up front so the inner loop has the data it
needs without extra queries. After the Export, the fields are available as
`Data.<Object>.*` (e.g. `Data.Account.*` and `Data.BillToContact.*`).

Rule of thumb — "does the join multiply rows for the base object?":

- **No** (1:1 / N:1) → add the fields to the upstream `Export`.
  Examples: Invoice→Account, Invoice→BillToContact, Subscription→Account,
  Invoice→DefaultPaymentMethod.
- **Yes** (1:N) → keep a separate task inside the loop. Examples:
  Invoice→InvoiceItem, Account→Subscription, Subscription→RatePlan,
  BillRun→Invoice.

**Anti-pattern (inefficient):**

```
Export Invoice → Iterate → Query Account → Query BillToContact → Query InvoiceItem → Email
```

**Preferred (one joined read + one per-parent query):**

```
Export Invoice (with Account + BillToContact fields) → Iterate → Query InvoiceItem → Email
```

```json
"parameters": {
  "fields": {
    "Invoice": ["Id", "InvoiceNumber", "Amount", "Balance", "DueDate", "Status"],
    "Account": ["Id", "Name", "AccountNumber", "Balance"],
    "BillToContact": ["Id", "FirstName", "LastName", "WorkEmail"]
  },
  "where_clause": "Invoice.SourceId = '{{Data.BillingRun.ID}}'"
}
```

**Important:** Do NOT include FK fields (e.g. `AccountId`, `BillToContactId`) under
`Invoice` — FK columns are SOAP-only and are not exportable via AQuA. The related
object data (`Account.*`, `BillToContact.*`) is already populated via the separate
`Account` and `BillToContact` keys in `fields`.

Inside the `Iterate` body, `Data.Account.*` and `Data.BillToContact.*`
are already populated from the Export — no inner Query needed. Use
`lookup_zuora_schema(object_name=<Object>, include_relationships=True)`
to confirm cardinality before deciding where a field belongs.

### Decision examples

**BATCH (run events):**

- "When bill run completes, send each invoice to ERP" → BATCH,
  `Export Invoice` (WHERE `SourceId = {{Data.BillingRun.ID}}`) → `Iterate`
  → `Query InvoiceItem` (inside loop) → `Callout`.
- "Get invoices from bill run with account details" → BATCH,
  `Data::Link` (JOIN).

**REALTIME (per-record events):**

- "When invoice is posted, email customer" → REALTIME,
  `Query Account` (by event `Data.Invoice.AccountId`) → `Email`.
- "When payment is processed, send confirmation email" → REALTIME,
  `Email` (event payload already has `Payment.Amount`,
  `BillToContact.WorkEmail`).
- "When subscription is created, provision in external system" →
  REALTIME, `Query Subscription` → `Callout`.

**General:**

- "Get all overdue invoices" → `Export` (polling / unknown volume).
- "Get invoice by ID from trigger" → `Query` (specific ID, guaranteed
  < 2000).
- "Count invoices by status" → `Export` with `GROUP BY`.
- "Recent payments" → `Export` (polling / time-based).
"""


def _lookup_data_retrieval() -> dict[str, Any]:
    return {
        "topic": "data_retrieval",
        "subtopic": None,
        "content": _DATA_RETRIEVAL_CONTENT,
        "data": {
            "decision_points": [
                "use_case_pattern",
                "record_count",
                "call_type",
                "cardinality",
            ],
        },
    }


# ---------------------------------------------------------------------------
# Topic: error_taxonomy (HTTP + Zuora error codes → root cause + next step)
# ---------------------------------------------------------------------------


_ERROR_TAXONOMY_ENTRIES: list[dict[str, str]] = [
    {
        "error": "SUBSCRIPTION_STATUS_NOT_ACTIVE",
        "root_cause": "Subscription is cancelled or suspended.",
        "resolution": "Verify subscription status (`Query Subscription` first) before amending.",
    },
    {
        "error": "DUPLICATE_SUBSCRIPTION_NUMBER",
        "root_cause": "Subscription key already exists.",
        "resolution": "Use a unique subscription number or let Zuora auto-assign one.",
    },
    {
        "error": "HTTP 401",
        "root_cause": "Bearer token expired or missing scope.",
        "resolution": "Re-authenticate via OAuth2; check that the client has the required scopes.",
    },
    {
        "error": "HTTP 403",
        "root_cause": "Missing `Zuora-Entity-Ids` on a multi-entity tenant, or missing scope.",
        "resolution": "Inject `Zuora-Entity-Ids` (and `Zuora-Org-Ids` if present) from session context into every request.",
    },
    {
        "error": "HTTP 404",
        "root_cause": "Wrong endpoint path or object does not exist.",
        "resolution": "Verify the path with `search_zuora_docs` or `lookup_zuora_api_spec(method=..., path=...)`.",
    },
    {
        "error": "HTTP 422",
        "root_cause": "Payload validation failure (missing required fields, invalid enum, etc.).",
        "resolution": "Call `validate_zuora_request(payload=..., endpoint=...)` before retrying.",
    },
    {
        "error": "HTTP 429",
        "root_cause": "Rate limit exceeded.",
        "resolution": "Read the `Retry-After` header; back off before retrying. Reduce parallelism if workflow-driven.",
    },
    {
        "error": "HTTP 5xx",
        "root_cause": "Transient Zuora backend error (rarely a payload issue).",
        "resolution": "Retry with exponential backoff. If it persists, surface the request-id (`Zuora-Track-Id`) to the user.",
    },
]


def _lookup_error_taxonomy() -> dict[str, Any]:
    lines = [
        "## Zuora Error Taxonomy",
        "",
        "Map an error to its **root cause** and **next step** — never just "
        "restate the error code to the user.",
        "",
        "| Error | Root Cause | Resolution |",
        "|---|---|---|",
    ]
    for entry in _ERROR_TAXONOMY_ENTRIES:
        lines.append(f"| `{entry['error']}` | {entry['root_cause']} | {entry['resolution']} |")
    lines += [
        "",
        "### Additional tools",
        "",
        "- `search_zuora_docs(query=<error>)` — full error-code reference.",
        "- `validate_zuora_request(payload=..., endpoint=...)` — run the same "
        "validator Zuora uses before replaying a 422.",
        "- `get_oauth_token_info(token=...)` — diagnose 401 errors.",
    ]
    return {
        "topic": "error_taxonomy",
        "subtopic": None,
        "content": "\n".join(lines),
        "data": {"entries": _ERROR_TAXONOMY_ENTRIES},
    }
