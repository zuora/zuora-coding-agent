# Zuora Workflow events reference

How `event_trigger` workflows are wired, what event names are accepted, and which Zuora REST endpoints inform the composer's choices.

This document is the authoritative ground truth for every key under `workflow.parameters.event_triggers` and `workflow.parameters.event_parameters`. The structured catalog lives in `workflow-enums.json` (`standard_events`, `event_parameters_schema`); this Markdown explains the *why* and shows derivation patterns.

## How an event-triggered workflow is wired

When `workflow.event_trigger: true`:

1. Zuora's Kafka consumer dispatches matching `BusinessEvent` records to all registered workflows. The match is name-based: `event_triggers[]` must contain the event's `name`.
2. For each matched event, Rails extracts the values listed in `event_parameters[*].params[]` and binds them into the workflow instance's `Data` scope under the configured `object` and `key`.
3. Tasks then access these values via Liquid: `{{ Data.<Object>.<Key> }}`.

So `event_parameters` is a contract: it tells Rails which event payload fields to pull off the wire and where to place them in `Data` so downstream tasks can read them.

## Where the standard event names come from

The hard-coded list lives in `app/javascript/components/WorkflowDefinitionForm.js` L150-219 (`defaultEvents`). It's the authoritative inventory of events that work out of the box with no custom registration. The full list is mirrored in `workflow-enums.json` -> `standard_events.events`.

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

## Two REST endpoints fed into the picker

The settings React component (`WorkflowSettingsForm`) calls two endpoints to populate the event UI. Both are reachable from the agent via either a direct `curl` call (credentials live in `~/.claude/settings.json -> env` as `ZUORA_BASE_URL`, `ZUORA_CLIENT_ID`, `ZUORA_CLIENT_SECRET`, and Claude Code injects them into every `Bash` invocation) or `mcp__zuora-mcp__ask_zuora` as a fallback. One-time OAuth exchange per session:

```bash
ACCESS_TOKEN=$(curl -sS -X POST "$ZUORA_BASE_URL/oauth/token" \
  --data-urlencode "grant_type=client_credentials" \
  --data-urlencode "client_id=$ZUORA_CLIENT_ID" \
  --data-urlencode "client_secret=$ZUORA_CLIENT_SECRET" \
  | jq -r '.access_token')
```

### 1. List available events

```bash
curl -sS "$ZUORA_BASE_URL/events/event-triggers" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq '.data[] | .eventType.name'
curl -sS "$ZUORA_BASE_URL/events/scheduled-events" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq '.data[] | .name'
```

Both are paginated (cursor in `body.next`). The settings UI concatenates them with the hard-coded `defaultEvents` and presents the combined list in alphabetical order.

Reference: `app/models/zuora_connect/app_instance.rb#get_custom_event_triggers` L1500-1525.

### 2. List available fields for one event

```bash
curl -sS "$ZUORA_BASE_URL/notifications/email-templates/info/selections?category=<category>" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq
```

Where `<category>` derives from the event metadata:

- If `event.id.length < 5` chars (i.e., a standard event id like `1410`): `category = event.id`.
- Otherwise (custom events): `category = ${event.namespace}:${event.name}` (e.g., `user.notification:MyCustomEvent`).

The response is a hash of object-name -> array-of-field-paths. The settings UI flattens these into `<...>` placeholder strings (e.g., `<BillingRun.Id>`, `<BillingRun.PostedDate>`) for the `value` field of `event_parameters[*].params[*]`.

Reference: `app/models/zuora_connect/app_instance.rb#get_custom_event_fields` L1452-1494 and `WorkflowSettingsForm.js` L383-401.

#### Field filtering rules

After fetching field options for an event:

- For **Standard** events (those in the `defaultEvents` list): exclude any returned field containing `DataSource`.
- For **Custom** events: include only fields containing `DataSource` OR matching `.${selBillEvent.baseObject}.`.

These rules come from `WorkflowSettingsForm.js` L388-400.

## Custom events

If the user references an event name not in the standard catalog and not in the corrections table, the workflow will not trigger until the event is registered. Three options:

1. **Manual registration** (recommended for one-off setups): Settings -> Notifications -> Custom Events in the Zuora UI.
2. **API registration** via `POST /events/event-triggers` with payload:
   ```json
   {
     "active": true,
     "baseObject": "Invoice",
     "condition": "Invoice.Status == 'Posted'",
     "eventType": {
       "name": "MyCustomInvoiceEvent",
       "displayName": "My Custom Invoice Event",
       "description": "Triggered when an invoice is posted with custom condition"
     }
   }
   ```
   Reference: `app/controllers/app_instance_controller.rb#create_custom_event` L68-81 and `app_instance.rb#create_custom_event_trigger` L1419-1450.
3. **Switch to a callout trigger** (often simpler): set `callout_trigger: true` instead of `event_trigger: true` and configure the corresponding standard Notification (Settings -> Notifications) to send a callout to the workflow's URL. This avoids needing to register a custom event.

## Composer recipe for an event-triggered workflow

For each event the user wants to react to:

1. **Resolve the canonical name.** Look up the user's intent in `standard_events.$canonical_name_corrections`, then in `standard_events.events`. If no match, fall to "Custom events" above.
2. **Add to `parameters.event_triggers[]`.** Append the canonical name string. Multiple events can share one workflow.
3. **Build the matching `parameters.event_parameters[*]` entry.** Shape:
   ```json
   {
     "eventName": "<canonical name>",
     "params": [
       { "object": "<baseObject>", "key": "Id", "value": "<<baseObject>.Id>" }
     ]
   }
   ```
   Add one `params[]` row per field that downstream tasks reference. For most workflows, binding `Id` is sufficient because subsequent `Query` / `Export` tasks use it in `where_clause`.
4. **Verify task references match.** Every `{{ Data.<Object>.<Key> }}` in downstream tasks must correspond to an `event_parameters[*].params[]` row with matching `object` and `key`.

### Worked example: react to bill run completion

User's natural-language request: "Run after a bill run completes; query the invoices in that run."

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
          { "object": "BillingRun", "key": "Id", "value": "<BillingRun.Id>" }
        ]
      }
    ]
  }
}
```

A downstream `Export` task can then use `where_clause: "BillRunId = '{{ Data.BillingRun.Id }}'"`.

**Provenance note.** `<BillingRun.Id>` is not a hard-coded special token; it is a merge-field string that the UI picker obtains from `GET /notifications/email-templates/info/selections?category=<category>` (see `get_custom_event_fields` in `app_instance.rb`). Before emitting this `value`, confirm the field via `curl` against the Notifications API (credentials are in `~/.claude/settings.json -> env`) or via `mcp__zuora-mcp__ask_zuora` — whichever channel the session has access to. Otherwise accept the linter's `W179` warning that the token is statically unverifiable. The linter also cross-checks that `BaseObject` (`BillingRun` here) matches the event's declared `baseObject` (`$event_base_objects.events["BillingRunCompletion"] = "BillingRun"`); a mismatch raises `E177`.

Similarly, the downstream `Export.parameters.where_clause` references `Invoice.BillRunId`. Confirm the column via `curl $ZUORA_BASE_URL/v1/describe/Invoice` (or MCP `ask_zuora`) before emission; it is also carried in the fallback `references/zuora-standard-fields.json` under `Invoice.fields` so lint stays quiet if neither channel is reachable.

## Pitfalls the linter catches

| Code | Rule |
|---|---|
| `E121` | `event_trigger == true` but `parameters.event_triggers[]` is empty or missing |
| `E122` | `event_trigger == true` but `parameters.event_parameters[]` is empty, missing, or has at least one entry whose `eventName` is not in `event_triggers[]` |
| `E120` | `parameters.event_parameters[*]` shape is wrong (missing `eventName`, missing/non-array `params`, or `params[*]` missing `object`/`key`/`value`) |
| `W121` | `event_triggers[]` contains a name that is not in the standard catalog and the MCP preflight (`GET /events/event-triggers`) did not confirm registration |
| `E177` | `event_parameters[*].params[*].value` uses the form `<BaseObject.Field>` where `BaseObject` does not match the event's declared `baseObject` (from `$event_base_objects.events`) and is not prefixed by `Event.` / `DataSource.` |
| `W179` | `event_parameters[*].params[*].value` is a `<...>` token that is neither a known special token (`$event_special_tokens.tokens`) nor a statically-verified `<BaseObject.Field>`; prompts the composer to fetch `GET /notifications/email-templates/info/selections?category=<category>` via MCP before emission |

## Related files

- `workflow-enums.json` -> `standard_events`, `event_parameters_schema`
- `zuora-standard-fields.json` -> `$event_base_objects.events`, `$event_special_tokens.tokens`
- `workflow-triggers-and-linkages.md` -> "Workflow-level field derivation by trigger style"
- `workflow-skeleton.json` -> default `parameters` shape with the always-present keys
- `scripts/lint-workflow-json.js` -> rules `E120`, `E121`, `E122`, `W121`, `E177`, `W179`
