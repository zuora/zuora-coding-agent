---
name: zuora-workflow-design
description: Design a Zuora Workflow-based solution
argument-hint: <business process to automate>
allowed-tools: [Read, Glob, Grep, Bash, Agent, mcp__zuora-mcp__manage_workflows, mcp__zuora-mcp__ask_zuora, mcp__zuora-mcp__query_objects]
---

Codex-only path resolution: When an instruction refers to `${CLAUDE_PLUGIN_ROOT}`, treat it as the root of this installed plugin. In Codex, resolve that root as the ancestor directory containing `skills/`, `references/`, and `.codex-plugin/`.


You are designing a Zuora Workflow-based automation solution. The user has described a business process they want to automate.

Design output is not an import artifact. Do not emit partial Workflow import JSON, abbreviated JSON, ellipsized task arrays, or "representative" JSON that could be copied into Workflow. If the user asks for JSON, either proceed with the `zuora-workflow-build` skill or explicitly hand off to it so the complete `.workflow.json` artifact can be composed, linted, and delivered.

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

Pick one or more trigger modes and confirm with the user if ambiguous. Each mode maps to one boolean flag on `workflow`, and Workflow supports multiple flags on a single setup:

- **Event-triggered** (`event_trigger`) — fires on a Zuora business event (e.g., `InvoicePosted`, `PaymentProcessed`, or tenant-custom events). Requires `parameters.event_triggers` + `parameters.event_parameters`.
- **Scheduled** (`scheduled_trigger`) — cron-based recurrence. Requires `interval` (cron) + `timezone` (Rails `ActiveSupport::TimeZone` friendly name, e.g. `"Pacific Time (US & Canada)"`). Do not use bare IANA names like `"America/Los_Angeles"` in the final JSON.
- **Callout-triggered** (`callout_trigger`) — external system POSTs to the workflow's callout URL.
- **On-demand** (`ondemand_trigger`) — user runs it manually from the Workflow UI or via API.

If the same business process and same task graph must run both manually and on a schedule, design one workflow with both `ondemand_trigger: true` and `scheduled_trigger: true`; do not create duplicate workflows with identical tasks. Split workflows only when trigger-specific inputs or branching make the task graphs meaningfully different. For scheduled runs, every required `parameters.fields[]` input needs a non-blank default because no user is prompted at schedule time.

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
- `${CLAUDE_PLUGIN_ROOT}/references/workflow-liquid-filters.md` — Workflow-specific Liquid filter signatures, argument counts/types, and examples from `filters.rb`.
- `${CLAUDE_PLUGIN_ROOT}/references/workflow-examples.md` — fully annotated workflow JSONs covering each trigger style.

### Step 5b: Elicit workflow-level fields

Before mapping tasks (Step 5a), confirm the workflow-envelope settings. Ask the user only what is not already implied. Cross-reference `workflow-triggers-and-linkages.md` -> "Workflow-level field derivation" for each answer.

1. **Trigger style(s)** (from Step 1a). Determines which trigger flags are `true` and what additional `parameters.*` keys are needed. Select every mode that should launch the same workflow:
   - `ondemand` -> no extra fields.
   - `callout` -> consider `parameters.fields[]` if the inbound POST body has a known schema. Often paired with a Zuora Notification configured to hit the workflow's callout URL (preferred over registering a custom event).
   - `scheduled` -> requires `interval` (6-token cron preferred) and `timezone` (Rails `ActiveSupport::TimeZone` friendly name). Translate the user's natural-language schedule (e.g., "weekdays at 8 AM Pacific") into the cron string + a Rails-friendly timezone such as `"Pacific Time (US & Canada)"`.
   - `event` -> requires `workflow.event_trigger: true`, `parameters.event_triggers[]`, and `parameters.event_parameters[]`. Resolve the event name through `workflow-enums.json` -> `standard_events.$canonical_name_corrections` first; if not in the standard catalog, treat the user-provided name as a custom event candidate, keep that exact registered name in `event_triggers[]`, and instruct the user that the custom event must be registered (Settings -> Notifications -> Custom Events, or `POST /events/event-triggers`). Do not drop the event trigger or switch trigger styles solely because the name is tenant-custom.
   - If multiple modes share one task graph, combine them in one workflow. Verify that any data consumed by shared tasks is available for every enabled trigger, or add defaults / a normalizer step before consuming trigger-specific data.
2. **Entity** (multi-entity tenants only). Ask which Zuora entity the workflow should run against. Skip in single-entity tenants — `Workflow::Setup.import` auto-fills.
3. **`call_type`**. Default `BATCH`. Switch only on explicit need: `REALTIME` for sub-second responsiveness, `UIACTION` for an embedded UI button, `SYNC` for synchronous callouts, `DATASTREAM` for streaming. Confirm tenant prerequisites are enabled (see call_type matrix).
4. **Notifications** (optional). Ask if the user wants email alerts on success / failure / pending. If yes, collect recipient list; emails may include Liquid templates like `{{Data.Account.WorkEmail__c}}`.
5. **Run prompt** (`parameters.fields[]`, optional). For ondemand/callout workflows that need typed input, define each field's `object_name`, `field_name`, `datatype` (one of `JSON | Boolean | Text | Integer | Decimal | Date | DateTime-Local | File-Field`), `required`, and `default`. Ordinary workflow-level inputs MUST use `object_name: "Workflow"` so they resolve as `Data.Workflow.<field_name>`; file uploads use `object_name: "Files"`. Do not invent grouping objects such as `BillRunConfig`; only use another `object_name` when it is a real supported object available in the run-prompt dropdown.

The Build skill will materialize these answers into the JSON; the Design skill's job is to pin them down.

### Step 5a: Map requirements to task types

Translate the business process into a linear / branching / iterating sequence of tasks. For each step, pick the correct `action_type` from the catalog:

- Data read/query: `Query` (≤ 2000 rows, synchronous, ZOQL — **default choice**; result lives in `Data.*`), `Export` (> 2000 rows or need a CSV/ZIP file), `GraphQuery` (joined/nested GraphQL reads; result in `Data.*`), `Data::Aqua` (async ZOQL bulk export — stateful/stateless AQuA jobs; always adds a file download step before data is usable; uses ZOQL, **not** SQL), `Data::Link` / Data Query (SQL-style row query; result lives in `Data.*` and can feed `Iterate`), `Data::BillingPreviewRun`.
- Iteration: `Iterate` (hooks `For Each`, `Complete`, `Failure`).
- Branching: `If` (`True` / `False`), `Logic::Case` (`Case_1` … `Case_N` / `Case_Else`).
- External integration: `Callout`, `AsynchronousCallout`.
- Notifications: `Email`, `Notifications::SMS`.
- CRUD: `Create`, `Update`, `Delete`, `CustomObject::*`.
- Amendments: `NewProduct`, `RemoveProduct`, `Suspend`, `Resume`, `Cancel` (legacy SOAP amendment tasks).

For subscription cancellation on the new API stack, design an Orders API `Callout` instead of the SOAP `Cancel` amendment task. The callout should target `{{ Credentials.zuora.rest_endpoint }}orders`, use `authorization.type = "zuora"`, and include an `orderActions[]` item with `type: "CancelSubscription"`. Use `Cancel` only when the user explicitly asks for a legacy SOAP amendment workflow.

Before adding multiple CRUD `Update` tasks, run a consolidation check: if the tasks target the same object and same `object_id` and only set different fields, design one `Update` task with all field values under `parameters.fields[<object>]`. Do not model any same-record object update as one CRUD task per field unless the user explicitly needs independent failure/retry handling, intermediate validation, or ordered side effects. ProductRatePlanCharge (PRPC) is the motivating example, but the rule is general.

**Subscription `PaymentTerm` with Flexible Billing:** When the requirement involves updating `PaymentTerm` on a subscription, always confirm with the user whether Flexible Billing is enabled on their tenant. On tenants with Flexible Billing enabled, updating `PaymentTerm` via a SOAP `Update` task on the `Subscription` object may not work as expected. If Flexible Billing is enabled, consult `mcp__zuora-mcp__ask_zuora` to determine the correct API path before choosing an implementation approach.
- Billing/Payment: `Billing::BillRun`, `InvoiceGenerate`, `WriteOff`, `Payment::PaymentRun`.
- Approval: `Approval` (`Approve` / `Reject` / `Failure`).

Before choosing `Billing::BillRun`, verify the bill-run filters fit the OOTB task. Use it for standard bill-run fields and v1 single-account/subscription filters (`AccountId` / `SubscriptionIds`). If the user asks for account-number filters, batch-number filters, APM/ProductRatePlanCharge ID filters, or any bill-run filter not supported by the OOTB task, design a custom Zuora `Callout` to the modern bill run API (`{{ Credentials.zuora.rest_endpoint }}bill-runs`) instead. Do not use the legacy object CRUD endpoint `/object/bill-run` for Create a bill run.

When a `Callout` / `AsynchronousCallout` targets a Zuora API, design it with `authorization.type = "zuora"` and only ordinary headers such as `Content-Type`. Do not design Zuora API callouts with `authorization.type = "none"`, `apiAccessKeyId` / `apiSecretAccessKey`, `Authorization`, or bearer-token headers; Workflow owns Zuora tenant credentials and entity context.

Use `Query`, not `Export`, when a later task needs direct workflow variables such as `Data.RatePlan.SubscriptionId`, `Data.Subscription.Id`, or `Data.Account.AccountNumber`. `Export` is a file-producing task: it writes `Data.Export.<object>` metadata plus `Data.Files.<file-holder>`, and row fields become `Data.<object>.<field>` only inside a downstream `Iterate` over that file holder.

Before adding multiple Data Query / `Data::Link` tasks, run a consolidation check:

- If one query only resolves scalar context for the next query (for example looking up `ProductRatePlanId` from a run-prompt `ProductRatePlanChargeId`), fold that lookup into the main query with a CTE and `CROSS JOIN`, then project the scalar columns on each output row.
- Do not insert `Data::Link -> Logic::Liquid(assign only) -> Data::Link` just to copy `Data.LinkRun.first.*` into `Data.Liquid.*`; downstream iterator/callout tasks should read the projected values as `row.<field>`.
- Keep separate queries only when the first result is reused by multiple branches, must stop/fail the workflow independently, produces a non-scalar collection, or cannot be expressed in the same SQL.

Before adding a `Logic::Liquid` task that loops over arrays, review `workflow-liquid.md` -> Filters and `workflow-liquid-filters.md` for exact signatures. If the step is simple row selection or grouping, design it with Workflow's built-in filters (`where`, `where_exp`, `group_by`, `group_by_exp`) instead of a manual `for` + `if` + `push` loop. Keep manual loops only for real row transformation or custom shape building.

Before adding a separate `Logic::Liquid` task, check whether it only prepares values for the next task. If the value is used once, inline the Liquid into that downstream task instead: date math in Export/Query predicates or task date fields, cancel/write-off decisions in `If` / `Logic::Case`, and request-body construction in a Callout `raw_body`. Keep a separate Liquid step only when it creates shared context for multiple tasks, normalizes a large reusable payload, or needs independent review/failure behavior.

Example shape for scalar context:

```sql
WITH expired_charge AS (
  SELECT
    id AS expiredchargeproductrateplanchargeid,
    productrateplanid
  FROM productrateplancharge
  WHERE id = '{{ Data.Workflow.ExpiredChargeProductRatePlanChargeId }}'
  LIMIT 1
)
SELECT
  i.id AS invoiceid,
  i.invoicenumber,
  expired_charge.productrateplanid,
  expired_charge.expiredchargeproductrateplanchargeid
FROM invoice i
CROSS JOIN expired_charge
WHERE i.balance > 0
```

When unsure, prefer a Tier 1 task type over a specialist.

**Transform/compute tasks — prefer `Logic::Liquid` and `Logic::JSONTransform` over `Script::JavaScript`.** Use `Script::JavaScript` only when the computation genuinely requires Node.js libraries or logic that Liquid cannot express. JavaScript is OPAQUE, has a 20 s default timeout, and requires an `_expected_response_schema` or `_opaque_trusted` declaration for any downstream `Data.*` references.

**Object query fields — only include fields the Zuora object actually supports.** Before listing fields or writing filter predicates in a `Query` or `Export` task, verify them against the live tenant describe endpoint or the bundled `references/zuora-standard-fields.json`. Invented field names are accepted by the JSON importer but raise `WorkflowError` at runtime. Custom fields must be confirmed by the user (they end in `__c` and vary per tenant). If a requested filter is not exposed by Object Query (for example `Subscription.InvoiceScheduleId`), choose a supported API/Data::Link path or ask the user for the supported relationship instead of designing an unsupported `Query.where_clause`.

### Step 5c: Trace data flow between tasks

Required reading: `workflow-data-flow.md` (especially sections 1, 2, and 9). Every Liquid `{{ Data.X.Y }}` reference must resolve against a topologically reachable upstream producer. Trace this in the design phase — the Build skill will enforce it again with a static walker, but catching gaps now saves a lint-fix loop.

For each task in your design, list two things:

1. **What it writes to `Data.*`** — look up its entry in `workflow-task-templates.json` → `data_contract.writes`. Resolve placeholders like `Data.{parameters.placement | self.object}` using the task's chosen `parameters.placement` (or default). Note the task's `data_contract.predictability`:
   - **DETERMINISTIC** — both the scope and the field shape are known at design time (e.g. `Query`, `Create`, `Update`, amendments, `InvoiceGenerate`).
   - **SEMI-DETERMINISTIC** — scope known, fields partially known (e.g. `Billing::BillRun`, `GraphQuery`, `Logic::Liquid`, `Reporting::*`, file-handling tasks).
   - **OPAQUE** — scope known, field shape unknowable until runtime (e.g. `Callout`, `AsynchronousCallout`, `Logic::Lambda`, `Script::JavaScript`, `Logic::JSONTransform`, `Logic::XMLTransform`, `Logic::CSVTranslator`, `Logic::ResponseFormatter`, `Execute::WorkflowTask`, `Mediation::SendEvents`).
   - **SCOPING** — no positive writes, just routes execution and/or rebinds (`If`, `Logic::Case`, `Iterate`, `Logic::Merge`, `Approval`, `Delete`, `CustomObject::Delete`).
   - **NONE** — side-effect only, no `Data.*` writes (`Email`, SMS, Kafka, Delay, Upload::*, UI::Stop/Page/WebShare, UsageMediation::*).

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

- **Trigger**: chosen mode (from Step 1a), plus required config (canonical event names from `workflow-events.md`, 6-token cron + Rails-friendly timezone, callout config).
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
- **External integrations**: Callout endpoints, auth mode, payload shape, validation status codes. For Zuora REST v1 endpoints, note that `Credentials.zuora.rest_endpoint` already includes the v1 base; designs should append only the resource path (`orders`, not `/v1/orders`).
- **Expected outcomes**: what changes in Zuora after successful execution.
- **Testing approach**: how to validate the workflow in sandbox (lint, dry-run `import_workflow activate=false` + `delete_workflow`, `manage_workflow_runs` `run_workflow` + `get_run_status` polling).
- **Next step**: Suggest `zuora-workflow-build` in Codex (or `/zuora-workflow-build` in Claude/Cursor) to compose the complete importable JSON artifact.

Do NOT implement the workflow in this skill. Focus on design and decision-making.
