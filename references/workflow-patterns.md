# Zuora Workflow Patterns

High-level design patterns plus the composition algorithm used by `/zuora-workflow-build`. For implementation details, follow the cross-references to the other reference docs.

## Overview

Zuora Workflows are JSON objects with four top-level sections: `workflow_definition`, `workflow`, `tasks`, and `linkages`. They execute as a directed graph starting from a single `Start` linkage. The Rails backend (`Workflow::Setup.import`) is strict: tasks / linkages arrays cannot be empty, every task needs a `parameters` object, and several top-level task columns (e.g., `object`, `object_id`) are ActiveRecord-validated at import.

Three files underpin safe composition:

- `workflow-skeleton.json` — the canonical empty envelope.
- `workflow-task-templates.json` — per-`action_type` templates with `required_params`, `required_at_import`, `param_enums`, and `hooks`.
- `workflow-enums.json` — shared enums, canonical linkage types, and typo hints.

Narrative references:

- `workflow-task-catalog.md` — the 71 `action_type` values grouped by category.
- `workflow-triggers-and-linkages.md` — trigger modes, `call_type`, linkage catalog.
- `workflow-liquid.md` — Liquid scopes (`Data`, `Credentials`, `WorkflowInstance`, `WorkflowSetup`, `TaskInstance`, `GlobalConstants`) and filter overview.
- `workflow-liquid-filters.md` — Workflow-specific Liquid filter signatures, argument counts/types, and examples.
- `workflow-examples.md` — three full, lint-clean workflow JSONs.

## Composition strategy: skeleton + templates

`/zuora-workflow-build` produces JSON by composing, not copy-editing. The steps:

1. **Start from a deep copy of `workflow-skeleton.json`.**
2. **Choose trigger mode(s)** — set at least one of `ondemand_trigger`, `callout_trigger`, `scheduled_trigger`, `event_trigger` to `true`. Multiple trigger flags are valid when the same task graph should run in more than one way, such as on-demand plus scheduled. Set `interval` + `timezone` for scheduled, and set `parameters.event_triggers` + `parameters.event_parameters` for event.
3. **Set `call_type`** (`BATCH` / `ASYNC` default; `SYNC`, `UI`, `DATASTREAM`, etc. only when a tenant-enabled mode is required).
4. **For each task**, deep-copy its template from `workflow-task-templates.json`, then:
   - Assign a unique integer `id`.
   - Fill every `<<REQUIRED: …>>` sentinel.
   - Populate every field in `required_at_import` (top-level `object` / `object_id` validated by ActiveRecord column presence).
   - Always include `parameters: {}` even if the task takes no parameters.
   - For `Logic::Case`, pre-normalize `parameters.case_condition` keys to `Case_1`, `Case_2`, … (sequential).
   - For Liquid expressions, use the scopes from `workflow-liquid.md`; keep `strict_variables: "true"`.
   - Position tasks on the canvas with the defaults in `workflow-enums.json.css_layout_defaults`.
5. **Emit linkages**:
   - Exactly one `Start` linkage (`source_workflow_id = workflow.id`, `source_task_id = null`).
   - One linkage per task-to-task edge; `linkage_type` must be one of the upstream task's published `hooks`.
   - `Case_N` linkages match the renumbered keys.
   - No `For Each` linkage on any path leading to a `Logic::Merge` task.
6. **Lint** via `scripts/lint-workflow-json.js`. Fix every error; address warnings when feasible.
7. **Optional sandbox dry-run**: `import_workflow` with `activate: false` in a sandbox, then `delete_workflow` to clean up. Rails has no `validate_only` flag, so "dry-run" means import-then-delete.

## Artifact delivery contract

Workflow import JSON must be delivered as a complete artifact. Do not provide partial, representative, or ellipsized JSON as the thing to import. The generated `.workflow.json` file must contain all four top-level import keys: `workflow_definition`, `workflow`, `tasks`, and `linkages`, and the lint command must be run against that exact file. If prerequisites prevent validation, explain what is missing and mark the artifact as not ready for import instead of filling gaps with hopeful JSON.

Workflow run-prompt fields also need import-safe defaults. For `workflow.parameters.fields[]` entries with `datatype: "JSON"`, never emit `default: null`; Rails validates JSON defaults by calling `.size`, so null, boolean, and numeric defaults crash import. Use `[]` for array inputs, `{}` for object/map inputs, or a valid JSON string/default.

## Pattern: Event-driven automation

Trigger on Zuora business events (`InvoicePosted`, `PaymentProcessed`, custom object events, etc.).

- `event_trigger: true`, all other trigger flags `false`.
- `parameters.event_triggers: [EventName]`.
- `parameters.event_parameters` maps event payload into `Data.<object>.<key>` so downstream tasks see `Data.Invoice.Id` etc.
- Make tasks idempotent — events can redeliver.
- See Use Case 1 and Use Case 3 in `workflow-examples.md`.

## Pattern: Scheduled batch processing

Run on a cron schedule.

- `scheduled_trigger: true`; `interval` is cron syntax; `timezone` is a Rails `ActiveSupport::TimeZone` friendly name such as `"UTC"` or `"Pacific Time (US & Canada)"`.
- Query the collection, Iterate, evaluate per-row logic, converge with the iterator's `Complete` hook (no `Logic::Merge` required for simple cases).
- For multi-branch fan-out under an Iterator, use `Logic::Case`; Rails serializes its keys to `Case_1..N` but the composer should pre-normalize so no linkages get destroyed.
- Use `zero_query_proceed: "true"` on `Query` to avoid aborting the workflow on empty result sets.
- See Use Case 2 in `workflow-examples.md`.

## Pattern: Consolidated Data Query With Scalar Context

When a workflow needs a row set plus one scalar lookup (for example a run-prompt `ProductRatePlanChargeId` that must resolve to `ProductRatePlanId`), prefer one `Data::Link` / Data Query task:

- Put the scalar lookup in a CTE.
- `CROSS JOIN` the one-row CTE into the main row query.
- Project the scalar columns onto every output row.
- In the iterator/callout body, reference those values as `row.<field>` instead of `Data.Liquid.<field>`.

Avoid this shape unless there is a clear reason:

```text
Data::Link scalar lookup -> Logic::Liquid assign-only copy -> Data::Link row query
```

Prefer this shape:

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
  a.accountnumber,
  s.name AS subscriptionnumber,
  i.id AS invoiceid,
  expired_charge.productrateplanid,
  expired_charge.expiredchargeproductrateplanchargeid
FROM invoice i
JOIN invoiceitem ii ON ii.invoiceid = i.id
JOIN subscription s ON s.id = ii.subscriptionid
JOIN account a ON a.id = i.accountid
CROSS JOIN expired_charge
WHERE i.balance > 0
```

Split the lookup into a separate query only when that first result is reused by multiple branches, needs independent `zero_result_stop` / failure behavior, produces a non-scalar collection, or cannot be expressed in the same SQL. The linter reports the avoidable chain as `W180`.

## Pattern: Prefer Workflow Liquid Filters

Before creating `Logic::Liquid` code that loops over a collection, check the filters documented in `workflow-liquid.md` and the exact signatures in `workflow-liquid-filters.md`, sourced from `rails/lib/liquid/filters.rb`.

- Use `where` for exact field selection, for example `{% assign active = Data.Subscription | where: "Status", "Active" %}`.
- Use `where_exp` for expression-based selection, for example `{% assign overdue = Data.Invoice | where_exp: "inv", "inv.Balance > 0" %}`.
- Use `group_by` / `group_by_exp` for bucketed results instead of constructing grouping hashes manually.
- Keep manual `for` loops when each row is transformed, enriched, or emitted into a custom shape that the filters cannot express.
- Avoid one-consumer Liquid shim tasks. If a Liquid task only calculates a date for the next Export, a boolean for the next `If` / `Logic::Case`, or a payload for the next Callout, inline the Liquid in that consuming task's parameter instead. The linter reports this as `W187`.

Avoid this shape for simple filtering:

```liquid
{% assign active = null | array %}
{% for sub in Data.Subscription %}
  {% if sub.Status == "Active" %}
    {% assign active = active | push: sub %}
  {% endif %}
{% endfor %}
```

Prefer this shape:

```liquid
{% assign active = Data.Subscription | where: "Status", "Active" %}
```

The linter reports obvious manual selection loops as `W184`.

## Pattern: Cancel Subscriptions With Orders API

For new-stack subscription cancellation, use a Zuora `Callout` to `{{ Credentials.zuora.rest_endpoint }}orders` with `authorization.type = "zuora"` and an `orderActions[]` item whose `type` is `"CancelSubscription"`; keep the legacy SOAP `Cancel` task only when explicitly requested. The linter reports legacy SOAP `Cancel` tasks as `W189`.

## Pattern: Multi-step approval flows

- `Approval` task publishes hooks `Approve`, `Reject`, `Failure`.
- Notify approvers via email or callout; wait for response; branch.
- Combine with `Logic::Case` when multiple approver tiers need routing.

## Pattern: External system integration via callouts

- Use `Callout` for sync HTTP calls to CRM / ERP / notification services.
- Use `AsynchronousCallout` for endpoints with long response times (polling model).
- Pull external integration URLs / credentials from `GlobalConstants.*`; pull Zuora URLs from `Credentials.zuora.*` and let `authorization.type = "zuora"` supply Zuora credentials.
- For Zuora REST v1 callouts, `Credentials.zuora.rest_endpoint` is already the v1 base URL. Use `{{ Credentials.zuora.rest_endpoint }}orders`, not `{{ Credentials.zuora.rest_endpoint }}/v1/orders` or `replace: "/v1/", ""` plus `/v1/orders`.
- For Zuora API callouts, set `parameters.authorization.type = "zuora"` and keep only ordinary headers such as `Content-Type`; do not add `apiAccessKeyId`, `apiSecretAccessKey`, `Authorization`, or bearer-token headers.
- Validate response status codes with `parameters.validation.status_codes: ["200", ...]` (string array!).
- `Callout#task_setup_validation` rejects some plain-text credential headers, but generated Zuora API callouts should use the built-in Zuora authorization mode rather than credential header Liquid.

## Pattern: Error handling

- Every task publishes a `Failure` hook — wire it to an error handler (notification, callout, dedicated error branch).
- `retry_rules.retry_count` 0..10; `retry_rules.retry_window` 0..60 seconds (Callout-class validation).
- For batch operations, route `For Each` → body → `Complete` and handle failed rows with a downstream `If` on `Data.<object>.success`.

### What is available on the Failure branch

When a task fails and its `Failure` hook fires, the `Data.*` scope contains only what was produced by **successfully completed upstream tasks** — the failed task's own output scope is **NOT** populated (it never completed). Safe references in an error handler are:

- Workflow-level seeds: `Data.Workflow.*`, event parameters, callout parameters.
- Output of any task that **fully completed** before the failed task (i.e., tasks on the upstream path whose hook was `Success`).
- `WorkflowInstance.*`, `WorkflowSetup.*`, `TaskInstance.*` — always populated.
- `GlobalConstants.*` — always populated.

**Do NOT reference** the failed task's own output scope in the error handler. For example, if a `Query Invoice` task fails, `Data.Invoice.*` is absent on the Failure path; using it in the error Email/Callout body will raise a `Liquid::UndefinedVariable` or silently render empty. Use `TaskInstance.name` or static strings to identify the failing step instead.

## Workflow discovery and management

Use `mcp__zuora-mcp__manage_workflows`:

- `workflow_guidance` — comprehensive capabilities and tenant-specific options.
- `match_workflows` — AI matching on business requirements.
- `list_workflows` — full tenant list.
- `get_workflow_details` — inspect tasks / triggers / parameters.
- `import_workflow` / `export_workflow` — promotion and backup.
- `delete_workflow` — cleanup after dry-run.

## Best practices

- Keep workflows focused — one business process per workflow.
- Name tasks descriptively (the UI and logs show `task.name`).
- Parameterize with `workflow.parameters.fields` for runtime inputs rather than hard-coding.
- Version with `workflow.version` (default `"0.0.1"`).
- Sandbox-first: import, activate, run, validate, then promote.
- Lint on every change; the linter is the front line of defense because `Task.import` skips `task_setup_validation`.
