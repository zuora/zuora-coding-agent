---
name: zuora-workflow-design
description: Design a Zuora Workflow-based solution
argument-hint: <business process to automate>
allowed-tools: [Read, Glob, Grep, Bash, Agent, mcp__zuora-mcp__manage_workflows, mcp__zuora-mcp__ask_zuora, mcp__zuora-mcp__query_objects]
---

Codex-only path resolution: When an instruction refers to `${CLAUDE_PLUGIN_ROOT}`, treat it as the root of this installed plugin. In Codex, resolve that root as the ancestor directory containing `skills/`, `references/`, and `.codex-plugin/`.


You are designing a Zuora Workflow-based automation solution. The user has described a business process they want to automate.

## Input

The user's automation requirement: $ARGUMENTS

## Workflow

### Step 1: Understand the business process

If the requirement is unclear, ask targeted questions:

- What business process needs automation?
- What Zuora objects are involved?
- What external systems need integration (CRM, ERP, notification services)?
- What is the expected volume and frequency?
- What should happen on failure?

### Step 1a: Clarify the trigger style

Pick exactly one trigger mode and confirm with the user if ambiguous. Each mode maps to one boolean flag on `workflow`:

- **Event-triggered** (`event_trigger`) — fires on a Zuora business event (e.g., `InvoicePosted`, `PaymentProcessed`, or tenant-custom events). Requires `parameters.event_triggers` + `parameters.event_parameters`.
- **Scheduled** (`scheduled_trigger`) — cron-based recurrence. Requires `interval` (cron) + `timezone` (IANA).
- **Callout-triggered** (`callout_trigger`) — external system POSTs to the workflow's callout URL.
- **On-demand** (`ondemand_trigger`) — user runs it manually from the Workflow UI or via API.

### Step 2: Get workflow guidance

Call `mcp__zuora-mcp__manage_workflows` with operation `workflow_guidance` to understand the full set of workflow capabilities, task types, and trigger options, including any tenant-specific `call_type` enablement (SYNC, UI, DATASTREAM).

### Step 3: Discover existing workflows

Call `mcp__zuora-mcp__manage_workflows`:

1. `match_workflows` with the user's requirement description — find workflows that match the business need (AI-powered matching).
2. `list_workflows` — see all workflows in the tenant for context.
3. `get_workflow_details` for any promising matches — inspect tasks, triggers, and parameters.

If a matching workflow exists, evaluate whether it can be reused, extended, or serves as a template.

### Step 4: Consult domain knowledge

Call `mcp__zuora-mcp__ask_zuora` for product-level questions about what can be automated and how Zuora handles the relevant business processes.

If relevant objects need inspection, use `mcp__zuora-mcp__query_objects` to check current tenant state.

### Step 5: Read reference docs

Read these in parallel for composition fluency:

- `${CLAUDE_PLUGIN_ROOT}/references/workflow-patterns.md` — composition strategy and patterns.
- `${CLAUDE_PLUGIN_ROOT}/references/workflow-task-catalog.md` — all 71 `action_type` values grouped by category, with format pitfalls.
- `${CLAUDE_PLUGIN_ROOT}/references/workflow-triggers-and-linkages.md` — trigger types, call_type matrix, linkage catalog, For-Each-before-Merge rule, and the **"Workflow-level field derivation"** cheat-sheet.
- `${CLAUDE_PLUGIN_ROOT}/references/workflow-events.md` — standard Zuora event catalog, `<canonical_name_corrections>` table, and how to use the MCP `ask_zuora` tool to verify custom-event registration.
- `${CLAUDE_PLUGIN_ROOT}/references/workflow-data-flow.md` — how `Data.*` is built and validated across tasks (per-task `data_contract` blocks, opaque-task protocol, walker algorithm). **Required reading before Step 5c.**
- `${CLAUDE_PLUGIN_ROOT}/references/workflow-liquid.md` — Liquid scopes for dynamic parameter values.
- `${CLAUDE_PLUGIN_ROOT}/references/workflow-examples.md` — fully annotated workflow JSONs covering each trigger style.

### Step 5b: Elicit workflow-level fields

Before mapping tasks (Step 5a), confirm the workflow-envelope settings. Ask the user only what is not already implied. Cross-reference `workflow-triggers-and-linkages.md` -> "Workflow-level field derivation" for each answer.

1. **Trigger style** (from Step 1a). Determines which trigger flag is `true` and what additional `parameters.*` keys are needed. The four mutually exclusive options:
   - `ondemand` -> no extra fields.
   - `callout` -> consider `parameters.fields[]` if the inbound POST body has a known schema. Often paired with a Zuora Notification configured to hit the workflow's callout URL (preferred over registering a custom event).
   - `scheduled` -> requires `interval` (6-token cron) and `timezone` (IANA name). Translate the user's natural-language schedule (e.g., "weekdays at 8 AM Pacific") into the cron string + tz.
   - `event` -> requires `parameters.event_triggers[]` and `parameters.event_parameters[]`. Resolve the event name through `workflow-enums.json` -> `standard_events.$canonical_name_corrections` first; if not in the standard catalog, instruct the user that a custom event must be registered (Settings -> Notifications -> Custom Events, or `POST /events/event-triggers`).
2. **Entity** (multi-entity tenants only). Ask which Zuora entity the workflow should run against. Skip in single-entity tenants — `Workflow::Setup.import` auto-fills.
3. **`call_type`**. Default `BATCH`. Switch only on explicit need: `REALTIME` for sub-second responsiveness, `UIACTION` for an embedded UI button, `SYNC` for synchronous callouts, `DATASTREAM` for streaming. Confirm tenant prerequisites are enabled (see call_type matrix).
4. **Notifications** (optional). Ask if the user wants email alerts on success / failure / pending. If yes, collect recipient list; emails may include Liquid templates like `{{Data.Account.WorkEmail__c}}`.
5. **Run prompt** (`parameters.fields[]`, optional). For ondemand/callout workflows that need typed input, define each field's `object_name`, `field_name`, `datatype` (one of `JSON | Boolean | Text | Integer | Decimal | Date | DateTime-Local | File-Field`), `required`, and `default`.

The Build skill will materialize these answers into the JSON; the Design skill's job is to pin them down.

### Step 5a: Map requirements to task types

Translate the business process into a linear / branching / iterating sequence of tasks. For each step, pick the correct `action_type` from the catalog:

- Data read: `Query`, `Export`, `GraphQuery`, `Data::Aqua`, `Data::BillingPreviewRun`, `Data::Warehouse`.
- Iteration: `Iterate` (hooks `For Each`, `Complete`, `Failure`).
- Branching: `If` (`True` / `False`), `Logic::Case` (`Case_1` … `Case_N` / `Case_Else`).
- External integration: `Callout`, `AsynchronousCallout`.
- Notifications: `Email`, `Notifications::SMS`.
- CRUD: `Create`, `Update`, `Delete`, `CustomObject::*`.
- Amendments: `NewProduct`, `RemoveProduct`, `Suspend`, `Resume`, `Cancel`.
- Billing/Payment: `Billing::BillRun`, `InvoiceGenerate`, `WriteOff`, `Payment::PaymentRun`.
- Approval: `Approval` (`Approve` / `Reject` / `Failure`).

When unsure, prefer a Tier 1 task type over a specialist.

### Step 5c: Trace data flow between tasks

Required reading: `workflow-data-flow.md` (especially sections 1, 2, and 9). Every Liquid `{{ Data.X.Y }}` reference must resolve against a topologically reachable upstream producer. Trace this in the design phase — the Build skill will enforce it again with a static walker, but catching gaps now saves a lint-fix loop.

For each task in your design, list two things:

1. **What it writes to `Data.*`** — look up its entry in `workflow-task-templates.json` → `data_contract.writes`. Resolve placeholders like `Data.{parameters.placement | self.object}` using the task's chosen `parameters.placement` (or default). Note the task's `data_contract.predictability`:
   - **DETERMINISTIC** — both the scope and the field shape are known at design time (e.g. `Query`, `Create`, `Update`, amendments, `InvoiceGenerate`).
   - **SEMI-DETERMINISTIC** — scope known, fields partially known (e.g. `Billing::BillRun`, `GraphQuery`, `Logic::Liquid`, `Reporting::*`, file-handling tasks).
   - **OPAQUE** — scope known, field shape unknowable until runtime (e.g. `Callout`, `AsynchronousCallout`, `Logic::Lambda`, `Script::JavaScript`, `Logic::JSONTransform`, `Logic::XMLTransform`, `Logic::CSVTranslator`, `Logic::ResponseFormatter`, `Execute::WorkflowTask`, `Mediation::SendEvents`).
   - **SCOPING** — no positive writes, just routes execution and/or rebinds (`If`, `Logic::Case`, `Iterate`, `Logic::Merge`, `Approval`, `Delete`, `CustomObject::Delete`).
   - **NONE** — side-effect only, no `Data.*` writes (`Email`, SMS, Kafka, Delay, Upload::*, UI::Stop/Page/WebShare, UsageMediation::*, `Data::Warehouse`).

2. **What `Data.X.Y` references it needs** — every Liquid expression in its `parameters` (URLs, body, where_clause, if_clause, case_clause, fields, headers).

#### Available-data trace

Build a small `available_data` table that grows as you walk down the graph. Start with the workflow seeds (see `workflow-data-flow.md` → "What's in Data before any task runs" and `workflow-enums.json` → `default_data_workflow_keys` / `trigger_seeding_rules`):

```
Step 0 (workflow seed):    Data.Workflow.{ExecutionDate, ExecutionDateTime, Name, Id, Tenant, User}
                         + Data.<event payload keys>     (event_trigger via parameters.event_parameters[])
                         + Data.<custom fields>          (ondemand/scheduled/callout via parameters.fields[])
                         + Data.Callout.<inbound body>   (callout_trigger only — OPAQUE)
                         + Data.UIAction.{ObjectId,…}    (UIACTION/SYNC_UI_ACTION call_type)
Step 1 (Query Invoice):  + Data.Invoice.{Id, InvoiceNumber, Amount, AccountId}        [DETERMINISTIC]
Step 2 (Iterate):          (no positive writes; rebinds Data.Invoice → single Hash inside For-Each)  [SCOPING]
Step 3 (Callout):        + Data.{placement | 'Callout'}                                [OPAQUE]
Step 4 (Email):            (no writes; just files Data.Files.<holder>)                  [NONE/file]
```

For every Liquid reference confirm:

- **The top-level scope** (e.g. `Invoice`, `Account`, `BillingRun`) is in `available_data` at this task's position. If not, REVISE the design (add an upstream Query, switch the trigger, fix `parameters.event_parameters`, etc.) — do not paper over with a hopeful reference.
- **The field name** (for DETERMINISTIC scopes) is in the upstream task's `data_contract.writes[].fields` (or in `parameters.fields[<object>]` for Query / Export / Create / Update / CustomObject::Query).
- **Inside an Iterate For-Each branch**, the iterated scope (e.g. `Data.Invoice`) is a single Hash, NOT an Array. References like `Data.Invoice[0].Id` or `Data.Invoice | size` won't work inside the loop.
- **After a `Logic::Merge`** following a `Logic::Case`, only scopes produced on **all** branches are reliably available. If you reference a scope written only on `Case_1`, it'll be missing on `Case_2`/`Case_Else` runs.

#### Opaque-task protocol

If your design includes a `Callout`, `AsynchronousCallout`, `Logic::Lambda`, `Script::JavaScript`, `Logic::JSONTransform`, `Logic::XMLTransform`, `Logic::CSVTranslator`, `Logic::ResponseFormatter`, `Execute::WorkflowTask`, or `Mediation::SendEvents` AND any downstream task references its output (e.g. `Data.Callout.acknowledgmentId`), the design phase MUST resolve which protocol to use. Ask the user one question per opaque task:

> Task `<task name>` is a `<action_type>` whose response shape we cannot statically know. You're about to reference `Data.<placement>.<field…>` downstream. Choose:
>
> **(a) Declare expected response schema** — list the fields you expect (e.g. `acknowledgmentId, receivedAt, errors[].code`). I'll add `parameters._expected_response_schema = { '<scope>': { ... } }` so the linter validates downstream references field-by-field.
>
> **(b) Opt out** — set `parameters._opaque_trusted = "true"` to suppress all `W172` lint warnings on `Data.<scope>.*` references and trust runtime.
>
> **(c) Insert a normalizer** — I'll add a `Logic::JSONTransform` (or `Logic::ResponseFormatter`) right after the opaque task that maps the response to a deterministic scope (e.g. `Data.NormalizedInvoice`). Downstream tasks then reference the normalized scope instead.
>
> **(d) Don't know yet** — I'll mark the design as "needs user confirmation before build" and pause.

Capture the answer in the design notes. The Build skill (Step 3e) will materialize it on the opaque task's `parameters` block. The leading underscore on the sentinel keys (`_opaque_trusted`, `_expected_response_schema`) means Rails ignores them — they're pure linter/composer metadata and never persisted server-side.

The Build skill enforces all of the above with the topological walker (Step 3d), backed by linter rules `E170` (missing scope), `W171` (field gap on deterministic), `W172` (unconfirmed opaque), `W173` (Iterate-body shape), `W174` (branch-partial scope after Logic::Merge).

### Step 6: Propose the design

Deliver a structured workflow design:

- **Trigger**: chosen mode (from Step 1a), plus required config (canonical event names from `workflow-events.md`, 6-token cron + IANA tz, callout config).
- **Workflow-level envelope**: `call_type`, `priority`, `delete_ttl`, `notifications`, multi-entity choice, and any non-default values from Step 5b.
- **Input parameters**: the `workflow.parameters.fields` the workflow expects at runtime (only relevant for callout/ondemand styles).
- **Steps**: ordered list of tasks. For each:
  - Name, `action_type`, purpose, expected inputs (from `Data.*` scope), expected outputs (where task writes per its `data_contract`).
  - Upstream linkages (which task feeds it, which `linkage_type`).
  - `required_at_import` values it must carry (`object`, `object_id` if applicable).
  - Parameters with Liquid references it will need.
  - **Data-flow notes** from Step 5c: what each task adds to `Data.*` (with `predictability`: deterministic / semi-deterministic / opaque / scoping / none) and which downstream tasks consume it. Flag every OPAQUE task (Callout / AsynchronousCallout / Logic::Lambda / Script::JavaScript / Logic::JSONTransform / Logic::XMLTransform / Logic::CSVTranslator / Logic::ResponseFormatter / Execute::WorkflowTask / Mediation::SendEvents) AND the agreed opaque-protocol choice (declare schema / opt out via `_opaque_trusted` / insert normalizer / pending user confirmation).
- **Decision points**: conditions for `If` / `Logic::Case` branches, including the exact `Case_N` keys when multi-way.
- **Iteration points**: `Iterate` tasks with the collection they iterate over and whether a `Logic::Merge` is needed (reminder: no `For Each` on any path reaching a Merge).
- **Error handling**: `Failure` branches, retry rules, fallback actions, notification on failure.
- **External integrations**: Callout endpoints, auth mode, payload shape, validation status codes.
- **Expected outcomes**: what changes in Zuora after successful execution.
- **Testing approach**: how to validate the workflow in sandbox (lint, dry-run `import_workflow activate=false` + `delete_workflow`, `run_workflows waitForCompletion=true`).
- **Next step**: Suggest `/zuora-workflow-build` to compose the JSON.

Do NOT implement the workflow in this skill. Focus on design and decision-making.
