# Zuora Workflow events reference

How `event_trigger` workflows are wired, what event names are accepted, and how agents discover or register custom events via Zuora MCP.

This document is the authoritative ground truth for every key under `workflow.parameters.event_triggers` and `workflow.parameters.event_parameters`. The structured catalog lives in `workflow-enums.json` (`standard_events`, `event_parameters_schema`); this Markdown explains the *why* and shows derivation patterns.

## How an event-triggered workflow is wired

When `workflow.event_trigger: true`:

1. Zuora's Kafka consumer dispatches matching `business event` records to all registered workflows. The match is name-based: `event_triggers[]` must contain the event's `name`.
2. For each matched event, Workflow extracts the values listed in `event_parameters[*].params[]` and binds them into the workflow instance's `Data` scope under the configured `object` and `key`.
3. Tasks then access these values via Liquid: `{{ Data.<Object>.<Key> }}`.

So `event_parameters` is a contract: it tells Workflow which event payload fields to pull off the wire and where to place them in `Data` so downstream tasks can read them.

## Where the standard event names come from

The hard-coded list is defined by `defaultEvents`. It's the authoritative inventory of events that work out of the box with no custom registration. The full list is mirrored in `workflow-enums.json` -> `standard_events.events`.

Highlights for common use cases:

| User intent | Canonical event name | baseObject |
|---|---|---|
| "After a bill run completes" | `BillingRunCompletion` | `BillingRun` |
| "After an invoice is posted" | `InvoicePosted` | `Invoice` |
| "After a payment is processed" | `PaymentProcessed` | `Payment` |
| "After a credit memo is posted" | `CreditMemoPosted` | `CreditMemo` |
| "After a payment run finishes" | `PaymentRunCompletion` | `Payment` |
| "After a journal run finishes" | `JournalRunCompletion` | `JournalRun` |
| "Subscription renewal coming up" | `UpcomingRenewal` | `Subscription` |
| "Payment method expiring" | `PaymentMethodExpiration` | `PaymentMethod` |

### Common name corrections

Natural-language requests rarely match canonical names exactly. Always check `workflow-enums.json` -> `standard_events.$canonical_name_corrections` before emitting:

| User said | Correct value |
|---|---|
| "BillRunCompleted" | `BillingRunCompletion` |
| "BillRunCompletedSuccess" | `BillingRunCompletion` |
| "BillingRunCompleted" | `BillingRunCompletion` |
| "InvoiceCreated" | `InvoicePosted` |
| "PaymentReceived" | `PaymentProcessed` |

If the user's event name does not appear in either the standard catalog or the corrections table, treat it as a **custom event** (see below).

## Discovering events and merge fields (MCP first)

Prefer Zuora MCP over Settings UI or raw `curl` for Events / Notifications operations that MCP covers.

### List / get custom event triggers

```
Tool: manage_event_triggers
operation: list_event_triggers
# optional filters: baseObject, eventTypeName, active, start, limit

Tool: manage_event_triggers
operation: get_event_trigger
eventTriggerId: <uuid>
```

Reuse the returned `eventType.name` (or create payload's `eventTypeName`) as the exact string in `parameters.event_triggers[]`.

Scheduled events remain discoverable via `GET /events/scheduled-events` (or `ask_zuora` as a fallback) when the user asks for a scheduled/custom schedule event that is not a custom event trigger.

### Merge-field selections for `event_parameters`

When composing `<Object.Field>` tokens for `event_parameters[*].params[*].value`, fetch:

```
GET /notifications/email-templates/info/selections?category=<category>
```

via credential-backed `curl` or `mcp__zuora-mcp__ask_zuora`. Category rules:

- Standard events (`event.id` length < 5): `category = event.id`
- Custom events: `category = ${event.namespace}:${event.name}` (e.g. `user.notification:MyCustomEvent`)

Field filtering:

- **Standard**: exclude fields containing `DataSource`
- **Custom**: keep fields containing `DataSource` OR matching `.${baseObject}.`

## Custom events

If the user references an event name not in the standard catalog and not in the corrections table, treat the name as a tenant-custom event candidate. Keep `workflow.event_trigger: true`, put the **exact registered** custom event name in `parameters.event_triggers[]`, and create a matching `parameters.event_parameters[*].eventName` entry.

**Default trigger style for ambiguous "custom event/callout" asks:** `event_trigger` (workflow listens to the registered custom event). Prefer creating/registering the custom event via MCP over switching to `callout_trigger`, unless the user explicitly wants inbound HTTP to the workflow callout URL.

### Preferred path — MCP (`manage_event_triggers`)

1. **List/match** existing triggers (`list_event_triggers` with `eventTypeName` / `baseObject`).
2. If missing, **propose create** and wait for explicit user confirmation before write:
   - `create_event_trigger` requires `active`, `baseObject`, `condition` (JEXL), `eventTypeName`, `eventTypeDisplayName`
   - Example condition: `changeType == 'UPDATE' && Invoice.Status == 'Posted' && Invoice.Status_old != 'Posted'`
3. Capture `eventTypeName` for workflow `event_triggers[]` and for downstream callout/notification binding.
4. Updates: `update_event_trigger` (id required; `baseObject` / `eventTypeName` immutable).

To **register or update** custom events, callout templates, and notification definitions, use `/zuora-event-notification-design` then `/zuora-event-notification-build` (confirm before writes). Those skills own:

| Step | MCP tool | Role |
|---|---|---|
| 1 | `manage_event_triggers` | Register/list/update custom event |
| 2 | `manage_callout_templates` | HTTPS action (URL/method/headers/auth); bind `eventTypeName` — optional |
| 3 | `manage_notification_definitions` | Bind event → `calloutTemplateIds`; set `calloutActive=true` — optional |

Workflow composition (listening with `event_trigger: true` and exact `event_triggers[]` name) stays in `/zuora-workflow-design` / `/zuora-workflow-build`. Hand off to event-notification skills when a custom event must be created/updated or when callout/notification resources are needed.

### When callout templates + notification definitions are needed

Use them when Zuora must **fire an HTTPS callout** (or email) when the event occurs — for example notifying an external system, or posting into a workflow's **callout URL**.

They are **not** required for a pure `event_trigger` workflow that only listens to Kafka business events. Do not invent a Notification → Callout bridge when a standard or registered custom event already drives the workflow.

### Callout-trigger alternative (explicit only)

Switch to `callout_trigger: true` (instead of / in addition to event listen) **only** when the user wants external or Notification POSTs into the workflow callout URL. Then configure a notification definition whose callout template targets that URL. Still prefer MCP (`manage_callout_templates` + `manage_notification_definitions`) over UI/curl.

UI/curl remain last-resort fallbacks when MCP tools are unavailable — not the primary guidance.

## Composer recipe for an event-triggered workflow

For each event the user wants to react to:

1. **Resolve the canonical or registered custom name.** Look up the user's intent in `standard_events.$canonical_name_corrections`, then in `standard_events.events`. If no match, treat the user-provided string as a custom event name and follow "Custom events" above; do not disable the event trigger solely because the name is tenant-custom.
2. **Preflight custom names** via `manage_event_triggers` `list`/`get` before emitting. If missing, propose create (confirm) rather than only relying on linter `W121`.
3. **Add to `parameters.event_triggers[]`.** Append the canonical standard name or exact registered custom event name string. Multiple events can share one workflow.
4. **Build the matching `parameters.event_parameters[*]` entry.** Shape:
 ```json
 {
 "eventName": "<canonical name>",
 "params": [
   { "object": "<baseObject>", "key": "Id", "value": "<<baseObject>.Id>" }
 ]
 }
 ```
 Add one `params[]` row per field that downstream tasks reference. For most workflows, binding `Id` is sufficient because subsequent `Query` / `Export` tasks use it in `where_clause`.
5. **Verify task references match.** Every `{{ Data.<Object>.<Key> }}` in downstream tasks must correspond to an `event_parameters[*].params[]` row with matching `object` and `key`.

### Worked example: react to bill run completion

User's natural-language request: "Run after a bill run completes; export the invoices in that run."

```json
{
 "ondemand_trigger": false,
 "callout_trigger": false,
 "scheduled_trigger": false,
 "event_trigger": true,
 "parameters": {
 "fields": [],
 "entity_name": null,
 "entity_id": null,
 "skipping_check": "db",
 "file_encryption": "false",
 "secure_error_msgs": "false",
 "show_run_prompt": null,
 "callout_response": "workflow instance",
 "event_triggers": ["BillingRunCompletion"],
 "event_parameters": [
 {
 "eventName": "BillingRunCompletion",
 "params": [
 { "object": "BillingRun", "key": "ID", "value": "<BillRun.ID>" }
 ]
 }
 ]
 }
}
```

A downstream `Export` task can then use `where_clause: "Invoice.SourceId = '{{ Data.BillingRun.ID }}'"`.

**Provenance note.** `<BillRun.ID>` is not a hard-coded special token; it is a merge-field string from the selections endpoint above. The `object` is `BillingRun` (Data scope) while the merge-field path prefix is `BillRun` (notifications payload). Confirm the field before emitting, or accept linter `W179`. The linter also cross-checks `BaseObject` against `$event_base_objects` / `$event_payload_path_prefix` (`E177`).

Similarly, the downstream `Export.parameters.where_clause` must use **`Invoice.SourceId`**, not `Invoice.BillRunId`. Confirm via describe or MCP; linter `W197` warns on `BillRunId` in `where_clause`.

### Payment run completion → bulk payment export

`PaymentRunCompletion` follows the same volume rule as bill runs: payment runs routinely create more than 2000 payments, so use **`Export`**, not **`Query`**, for the parent `Payment` collection. Bind the run id from `event_parameters` or from `Data.PaymentRun.Id` when the workflow created the run, then scope the export with a run filter confirmed via describe. Follow with `Iterate` over the export file holder. Per-payment child reads inside the For Each branch may still use `Query` when each child set is small.

## Pitfalls the linter catches

| Code | Rule |
|---|---|
| `E007` | `event_trigger == true` but `parameters.event_triggers[]` is empty or missing |
| `E122` | `event_trigger == true` but `parameters.event_parameters[]` is empty, missing, or has at least one entry whose `eventName` is not in `event_triggers[]` |
| `E120` | `parameters.event_parameters[*]` shape is wrong (missing `eventName`, missing/non-array `params`, or `params[*]` missing `object`/`key`/`value`) |
| `W121` | `event_triggers[]` contains a name that is not in the standard catalog and MCP preflight (`manage_event_triggers` / event-triggers list) did not confirm registration |
| `W123` | `event_triggers[]` or `event_parameters[]` is populated but `workflow.event_trigger` is not `true`, so the configured event will not launch the workflow |
| `E177` | `event_parameters[*].params[*].value` uses the form `<BaseObject.Field>` where `BaseObject` does not match the event's declared `baseObject` (from `$event_base_objects.events`) and is not prefixed by `Event.` / `DataSource.` |
| `W179` | `event_parameters[*].params[*].value` is a `<...>` token that is neither a known special token (`$event_special_tokens.tokens`) nor a statically-verified `<BaseObject.Field>`; prompts the composer to fetch merge-field selections before emission |

## Related files

- `workflow-enums.json` -> `standard_events`, `event_parameters_schema`
- `zuora-standard-fields.json` -> `$event_base_objects.events`, `$event_special_tokens.tokens`
- `workflow-triggers-and-linkages.md` -> "Workflow-level field derivation by trigger style"
- `workflow-skeleton.json` -> default `parameters` shape with the always-present keys
- Skills: `zuora-event-notification-design`, `zuora-event-notification-build` (events/callouts/notifications); `zuora-workflow-*` (workflow composition)
