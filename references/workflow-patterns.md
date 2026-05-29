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
- `workflow-liquid.md` — Liquid scopes (`Data`, `Credentials`, `WorkflowInstance`, `WorkflowSetup`, `TaskInstance`, `GlobalConstants`).
- `workflow-examples.md` — three full, lint-clean workflow JSONs.

## Composition strategy: skeleton + templates

`/zuora-workflow-build` produces JSON by composing, not copy-editing. The steps:

1. **Start from a deep copy of `workflow-skeleton.json`.**
2. **Choose a trigger** — set exactly one of `ondemand_trigger`, `callout_trigger`, `scheduled_trigger`, `event_trigger` to `true`; set `interval` + `timezone` for scheduled, set `parameters.event_triggers` + `parameters.event_parameters` for event.
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

## Pattern: Event-driven automation

Trigger on Zuora business events (`InvoicePosted`, `PaymentProcessed`, custom object events, etc.).

- `event_trigger: true`, all other trigger flags `false`.
- `parameters.event_triggers: [EventName]`.
- `parameters.event_parameters` maps event payload into `Data.<object>.<key>` so downstream tasks see `Data.Invoice.Id` etc.
- Make tasks idempotent — events can redeliver.
- See Use Case 1 and Use Case 3 in `workflow-examples.md`.

## Pattern: Scheduled batch processing

Run on a cron schedule.

- `scheduled_trigger: true`; `interval` is cron syntax; `timezone` is IANA.
- Query the collection, Iterate, evaluate per-row logic, converge with the iterator's `Complete` hook (no `Logic::Merge` required for simple cases).
- For multi-branch fan-out under an Iterator, use `Logic::Case`; Rails serializes its keys to `Case_1..N` but the composer should pre-normalize so no linkages get destroyed.
- Use `zero_query_proceed: "true"` on `Query` to avoid aborting the workflow on empty result sets.
- See Use Case 2 in `workflow-examples.md`.

## Pattern: Multi-step approval flows

- `Approval` task publishes hooks `Approve`, `Reject`, `Failure`.
- Notify approvers via email or callout; wait for response; branch.
- Combine with `Logic::Case` when multiple approver tiers need routing.

## Pattern: External system integration via callouts

- Use `Callout` for sync HTTP calls to CRM / ERP / notification services.
- Use `AsynchronousCallout` for endpoints with long response times (polling model).
- Pull URL / credentials from `GlobalConstants.*` and `Credentials.zuora.*`, never hard-code.
- Validate response status codes with `parameters.validation.status_codes: ["200", ...]` (string array!).
- `Callout#task_setup_validation` rejects plain-text apiAccessKeyId / apiSecretAccessKey header values; use `{{ Credentials.zuora.username }}` form.

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
