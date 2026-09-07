---
name: zuora-workflow-verify
description: Import a lint-clean workflow to sandbox, test-run it via MCP, poll task status, and fix plan/build issues in a bounded loop
argument-hint: <workflow.json path or name, optional plan path, optional test inputs>
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash, Agent, AskUserQuestion, mcp__zuora-mcp__manage_workflows, mcp__zuora-mcp__manage_workflow_runs, mcp__zuora-mcp__ask_zuora, mcp__zuora-mcp__query_objects]
---

Codex-only path resolution: When an instruction refers to `${CLAUDE_PLUGIN_ROOT}`, treat it as the root of this installed plugin. In Codex, resolve that root as the ancestor directory containing `skills/`, `references/`, and `.codex-plugin/`.


You verify a Zuora Workflow end-to-end in the tenant: import → run → poll → diagnose failures → fix at the **plan** layer → rebuild → relint → retry until success or `max_fix_retries` is exhausted.

## Input

$ARGUMENTS — typically a lint-clean `.workflow.json` path, the matching `.plan.json` path, and optional test-run inputs (workflow field values, callout payload, entity scope).

## Preconditions (hard gates)

Stop and explain what is missing if any gate fails:

1. **MCP available** — `mcp__zuora-mcp__manage_workflows` and `mcp__zuora-mcp__manage_workflow_runs` must be callable. If not, point the user to `${CLAUDE_PLUGIN_ROOT}/skills/zuora-context/SKILL.md` MCP setup.
2. **Lint-clean artifact** — run `node ${CLAUDE_PLUGIN_ROOT}/scripts/lint-workflow-json.js <workflow.json>` and require exit code 0 before importing. If lint fails, hand off to `zuora-workflow-build` (fix plan → rebuild → relint) first.
3. **Plan artifact** — a `.plan.json` sibling or explicit path is required for the fix loop. Fixes must never patch `.workflow.json` by hand.
4. **Tenant target** — default assumption: sandbox/non-production. Do not verify against production unless the user explicitly names production and acknowledges impact.
5. **User confirmation (hard gate)** — see **Step 2e** below. Never call `import_workflow` or `run_workflow` without explicit approval.
6. **Runnable trigger** — classify before run (see **Event-triggered workflows** below):
   - **On-demand** (`ondemand_trigger`) — run with `parameters.fields[]` / plan `input_fields`.
   - **Event + BATCH** (`event_trigger` + `ondemand_trigger` + `call_type: BATCH`) — runnable on-demand **only after event context is seeded** (mirror fields + `query_objects`, or user-supplied ids). Do not run until `Data.<EventObject>.<key>` values are resolved.
   - **Callout-triggered** (`callout_trigger`) — supply a test POST body matching `parameters.fields[]`.
   - **Scheduled** — only if every required `parameters.fields[]` entry has a non-blank default.
   - **Event-only** (`event_trigger` with no `ondemand_trigger` and no `callout_trigger` — typical for `REALTIME` / `UIACTION`) — **import + lint only**; stop before `run_workflow` and offer real-event verification or a plan redesign with mirror test inputs. Do not pretend to auto-run.

## User confirmation (hard gate)

**Never import or run a workflow without explicit user approval.** This applies even when:

- The user invoked `/zuora-workflow-verify` or said "test in sandbox"
- Build handed off to verify in the same session
- A previous attempt failed and you are retrying after a plan fix

Use `AskUserQuestion` (or an equivalent explicit yes/no) — do not infer consent from vague language like "go ahead" without showing the run plan.

### What requires confirmation

| MCP operation | When | Required? |
| --- | --- | --- |
| `import_workflow` | Before every import (including re-import after fix) | **Yes** |
| `run_workflow` | Before every test run (including each retry attempt) | **Yes** |
| `get_run_status` | Polling an already-started run | No |
| `delete_workflow` | Cleanup of `agent-verify-*` imports | No — unless user opted to keep workflows |

If the user declines import or run, stop verify, set `.verify.json` → `status: "cancelled"`, and report what was skipped.

### What to show before asking

Present a short **verify plan** the user can approve:

- Workflow name and artifact paths (`plan`, `workflow`)
- Connected tenant (`ZUORA_BASE_URL` or environment the user named)
- `trigger_class` and whether a test run will execute (or import-only for `event_only`)
- Planned import name (`agent-verify-<basename>-<timestamp>`)
- **Side-effect summary** — list task types that will execute (Export, Query, Callout, Email, CRUD, etc.) and external callout URLs if any
- `test_inputs` / `event_context_resolved` (ids discovered via `query_objects`)
- Mirror `input_fields` added for event testing (if any)

Example prompt:

> Ready to verify **BillRunInvoiceCallout** in sandbox. I will import as `agent-verify-bill-run-invoice-callout-…`, then run on-demand with `BillingRun.ID = <id>`. Tasks: Export Invoice → Iterate → Query InvoiceItem → Callout to `https://…`. This may read tenant data and call external URLs. Proceed with import and test run?

Offer at least: **Proceed**, **Import only (no run)**, **Cancel**.

Record the user's choice in `.verify.json` → `user_confirmed_import`, `user_confirmed_run`, and `history[]`.

Before import, call **both** in parallel:

```
mcp__zuora-mcp__manage_workflows       { "operation": "workflow_guidance" }
mcp__zuora-mcp__manage_workflow_runs   { "operation": "run_guidance" }
```

Use the live guidance responses as the authoritative map for `import_workflow`, `delete_workflow`, `run_workflow`, `get_run_status`, and related operations. Do not rely on stale parameter names.

## Defaults

| Setting | Default |
| --- | --- |
| `max_fix_retries` | `3` |
| Import name prefix | `agent-verify-` |
| `activate_version` on import | `true` (workflow must be active to run) |
| Poll interval | `15` seconds |
| Poll timeout | `20` minutes (extend for bill-run / export / async callout workflows after telling the user) |
| Cleanup after pass | Ask user; default **keep** on success, **delete** on verify-only dry-run when user asked not to keep |

## Verify loop

Write a running log to `${CLAUDE_PLUGIN_ROOT}/output/<name>.verify.json` (create or append each attempt):

```jsonc
{
  "workflow_json": "output/<name>.workflow.json",
  "plan_json": "output/<name>.plan.json",
  "attempt": 1,
  "max_fix_retries": 3,
  "import_name": "agent-verify-<name>-<timestamp>",
  "workflow_id": null,
  "run_id": null,
  "status": "running",
  "trigger_class": "ondemand | event_batch_runnable | event_only | callout | scheduled",
  "event_context_required": [],
  "event_context_resolved": {},
  "mirror_input_fields_added": false,
  "user_confirmed_import": false,
  "user_confirmed_run": false,
  "history": []
}
```

## Event-triggered workflows

Event runs seed `Data.<object>.<key>` **only** from `workflow.parameters.event_parameters[]` — not from the full Kafka payload. On-demand runs seed **only** from `workflow.parameters.fields[]` (plan `input_fields`). A manual run on an event workflow therefore fails at the first `Data.BillingRun.ID`-style reference unless you supply equivalent context.

Required reading: `${CLAUDE_PLUGIN_ROOT}/references/workflow-data-flow.md` (section 3) and `${CLAUDE_PLUGIN_ROOT}/references/workflow-enums.json` → `trigger_seeding_rules`.

### Classify the workflow

Read `workflow.event_trigger`, `workflow.ondemand_trigger`, `workflow.callout_trigger`, and `workflow.call_type` from the linted JSON:

| Shape | `trigger_class` | Verify run? |
| --- | --- | --- |
| `event_trigger` + `ondemand_trigger` + `call_type: BATCH` | `event_batch_runnable` | Yes — after event context seeding (below) |
| `event_trigger` only (no on-demand/callout) | `event_only` | Import/lint only; offer real-event test |
| `ondemand_trigger` (no event) | `ondemand` | Yes — ordinary field inputs |
| `callout_trigger` | `callout` | Yes — test POST body |

BATCH event workflows get `ondemand_trigger: true` from the assembler by design — that does **not** mean event data is present on a manual run.

### Step 2a: Extract required event context

From `workflow.parameters.event_parameters[]`, build `event_context_required`:

```jsonc
// Each entry: { "object": "BillingRun", "key": "ID", "data_path": "Data.BillingRun.ID" }
```

Use every `params[]` item: `object`, `key`, and `data_path = Data.{object}.{key}`.

If the workflow is `event_batch_runnable` and this list is non-empty, event context seeding is **mandatory** before Step 4.

### Step 2b: Resolve event context (auto-discover first)

Resolve each required `{object, key}` in order:

1. **User-provided** — if `$ARGUMENTS` or `.verify.json` already has `event_context_resolved`, use it.
2. **`query_objects`** — discover a recent tenant record (sandbox). Prefer completed/success states and records that will satisfy downstream Export/Query filters.

| Event (examples) | Primary object | Discovery hint |
| --- | --- | --- |
| `BillingRunCompletion` | `BillingRun` | Recent bill run with `Status = 'Completed'`; prefer one that has invoices (`Invoice.SourceId`) |
| `PaymentRunCompletion` | `PaymentRun` | Recent completed payment run |
| `JournalRunCompletion` | `JournalRun` | Recent completed journal run |
| `InvoicePosted` / `InvoiceDue` | `Invoice` | Recent posted invoice (+ `Account` if also in `event_parameters`) |
| `PaymentProcessed` / `PaymentDeclined` | `Payment` | Recent processed payment (+ related `Account` if bound) |
| `SubscriptionCreated` / `UpcomingRenewal` | `Subscription` | Active subscription |

Example:

```
mcp__zuora-mcp__query_objects — object BillingRun, filter Status = Completed, limit 5, order by CreatedDate desc
```

Pick the first id that downstream tasks can use (e.g. a bill run that actually has invoices when the workflow exports invoices). Record in `.verify.json` → `event_context_resolved`.

3. **Ask the user** — only when discovery returns nothing usable. Do not invent ids.

### Step 2c: Mirror `input_fields` when missing (sandbox test path)

On-demand runs do not read `event_parameters`. To pass discovered context into a manual `run_workflow`, ensure the plan exposes the same `Data.<object>.<key>` paths via `input_fields`.

**Before import**, inspect plan `input_fields[]`. For each `event_context_required` entry, check whether an existing field already seeds the same path (`object_name` + `field_name` matching `object` + `key`).

If missing, **append mirror fields to the plan** (then rebuild + relint before import):

```jsonc
{
  "field_name": "ID",
  "object_name": "BillingRun",
  "datatype": "String",
  "required": false,
  "default": ""
}
```

Rules for mirror fields:

- Use the **same `object_name` and `field_name`** as the `event_parameters` binding (`BillingRun` + `ID` → `Data.BillingRun.ID`).
- `required: false` — production event runs do not prompt; sandbox verify supplies the value at run time.
- `datatype: "String"` unless the key is clearly numeric/date.
- Set `.verify.json` → `mirror_input_fields_added: true` and note in `history` which fields were added.
- Re-run validate → build → lint after editing the plan (same as Step 6 fix procedure).
- Tell the user mirror fields are **for sandbox verification**; production still relies on the event trigger.

**Do not** add a `Logic::Liquid` shim solely to copy test ids unless multiple branches need the same normalized scope — mirror fields are simpler and match Zuora's on-demand seeding model.

### Step 2d: Build `test_inputs` for `run_workflow`

Merge:

- Ordinary `parameters.fields[]` / plan `input_fields` (workflow-scoped prompts).
- **Mirror event context** — for each resolved `{object, key, value}`, include a run input that maps to `object_name` + `field_name` (per `run_guidance`).

Example for `BillingRun.ID`:

```jsonc
"test_inputs": {
  "fields": [
    { "object_name": "BillingRun", "field_name": "ID", "value": "<discovered-bill-run-id>" }
  ]
}
```

Record the full `test_inputs` object in `.verify.json`.

### Optional: real-event verification (Step 8)

After a **passed** manual verify run, offer a final gate when the user wants production fidelity. **Require separate explicit confirmation** before triggering any real business action (bill run, invoice post, etc.) — do not fire events automatically.

1. Present what will be triggered and expected side effects; wait for approval.
2. Trigger the real business action in sandbox (e.g. run a small bill run).
3. Wait for the workflow to fire on the event (or list recent runs via MCP).
4. Poll `get_run_status` on the event-fired instance.
5. Fix plan from any event-only failures (payload shape, timing, async jobs).

Do not block manual verify on real-event success — treat it as an optional follow-up.

### Step 1: Resolve artifacts

1. Resolve `<workflow.json>` from `$ARGUMENTS` or the latest `output/*.workflow.json` the user named.
2. Resolve matching `<plan.json>` (same basename, `.plan.json` extension).
3. Lint the workflow JSON (must pass).

### Step 2: Collect test inputs

Before the first import, ensure run inputs are known:

1. **Classify trigger** — set `.verify.json` → `trigger_class` (see **Event-triggered workflows**).
2. **Event context** — if `event_batch_runnable`, run **Steps 2a–2d** (extract → discover → mirror fields → `test_inputs`).
3. **Ordinary fields** — read `workflow.parameters.fields[]` (or plan `input_fields`). For each required field without a default, ask the user OR discover via `query_objects`.
4. **Callout** — synthesize a minimal inbound body for `callout_trigger` workflows.
5. Record everything in `.verify.json` under `test_inputs` and `event_context_resolved`.

### Step 2e: Confirm with the user (hard gate)

After Steps 2–2d, **stop** and present the verify plan (see **User confirmation**). Wait for explicit approval before Step 3.

- If the user chooses **Import only** — set `user_confirmed_import: true`, `user_confirmed_run: false`, run Step 3, then skip Step 4–5 and report.
- If the user chooses **Proceed** — set both confirmation flags `true` and continue to Step 3 then Step 4.
- If the user chooses **Cancel** — set `status: "cancelled"` and stop.

On fix-loop retries (`attempt > 1`), present an updated verify plan (what changed in the plan, new test ids if any) and **ask again** before re-import and before the next `run_workflow`. Do not auto-retry tenant operations.

### Step 3: Import

**Gate:** `user_confirmed_import` must be `true`. If not, return to Step 2e.

Call `mcp__zuora-mcp__manage_workflows` → `import_workflow`:

- Pass the full linted JSON (all four envelope keys).
- `name`: `agent-verify-<basename>-<YYYYMMDD-HHMMSS>` (or user override).
- `activate_version`: `true` unless guidance says otherwise.

On import failure → **Step 6 (fix)** with `failure_phase: import`.

On success, record `workflow_id` / definition id from the response in `.verify.json`.

### Step 4: Run

**Gate:** `user_confirmed_run` must be `true`. If the user approved import-only, skip this step. If not confirmed, return to Step 2e — **never** call `run_workflow` speculatively.

Call `mcp__zuora-mcp__manage_workflow_runs` → `run_workflow`:

- Target the imported workflow id/name from Step 3.
- Pass `test_inputs` as field values / callout payload per `run_guidance`.

On run failure to start → **Step 6** with `failure_phase: run_start`.

Record `run_id` / instance id.

### Step 5: Poll until terminal

Loop `get_run_status` every `poll_interval` seconds until:

- **Success** — workflow run completed without failed tasks → **Step 7 (report pass)**.
- **Failed** — any task in `Error` / `Failed` / non-success terminal state → capture task id, name, `action_type`, error message, `error_class`, and `error_details` → **Step 6** with `failure_phase: runtime`.
- **Timeout** — report partial status, last known task, and ask whether to extend timeout or stop.

When inspecting status, map failed tasks back to plan task `name` / `id` using the plan's `tasks[]` array.

### Step 6: Fix (bounded)

Increment `attempt`. If `attempt > max_fix_retries`, stop and report unresolved issues with the last error payload.

Otherwise classify the failure and fix the **plan**:

| Phase | Symptom | Fix target |
| --- | --- | --- |
| `import` | Missing `required_at_import`, bad `call_type`, AR validation, empty tasks/linkages | Plan task parameters / trigger / `call_type` |
| `import` | Unknown field in Export/Query/Create/Update | Re-describe object; fix `parameters.fields` / `where_clause` in plan |
| `import` | Invalid event parameter / linkage | Plan `trigger.event_parameters` or linkage `linkage_type` |
| `run_start` | Missing required workflow input | Add default in plan `input_fields` or supply `test_inputs` |
| `run_start` | Workflow inactive / not found | Re-import with `activate_version: true` |
| `runtime` | ZOQL/SOQL field error | Fix plan query/export fields after describe |
| `runtime` | Liquid error / nil `Data.*` | Fix plan Liquid paths; check Export vs Query vs Iterate |
| `runtime` | Callout 4xx/5xx | Fix plan URL, auth (`authorization.type = "zuora"`), `raw_body`, `ResponseBody` paths |
| `runtime` | Zuora API async job not complete | Add/status-poll pattern in plan (`W195`) |
| `runtime` | Missing tenant data ("record not found") | Re-run `query_objects` for event context; ask user for valid ids — do not invent |
| `runtime` | Export 0 rows on event workflow | Wrong `Data.<EventObject>.<key>` at manual run — fix mirror `input_fields` / `test_inputs` |
| `runtime` | External callout unreachable | Ask user for mock URL or skip callout task — do not mask |
| `runtime` | Manual pass, event fail | Fix `event_parameters` tokens; run optional real-event gate (Step 8) |

Fix procedure:

1. Edit `output/<name>.plan.json` (not `.workflow.json`).
2. Re-validate: `${CLAUDE_PLUGIN_ROOT}/bin/workflow-engine validate-plan --stage plan -i output/<name>.plan.json` until `ok: true`.
3. Rebuild: `${CLAUDE_PLUGIN_ROOT}/bin/workflow-engine build -i output/<name>.plan.json -o output/<name>.workflow.json`.
4. Relint: `node ${CLAUDE_PLUGIN_ROOT}/scripts/lint-workflow-json.js output/<name>.workflow.json` until exit 0.
5. Delete the previous `agent-verify-*` workflow if it still exists (`delete_workflow`).
6. **Re-confirm with the user** (Step 2e) — reset `user_confirmed_import` / `user_confirmed_run` to `false` until they approve the retry.
7. Go to **Step 3** with `attempt + 1`.

Never hand-edit assembled import JSON except explicit user-requested post-build edits (then relint).

### Step 7: Report

On success, set `.verify.json` `status` to `passed` and report:

- Saved artifact paths (`plan`, `workflow`, `verify` log).
- Import name and workflow id.
- Run id and duration.
- Task-level summary (which tasks ran, key outputs if present in status).
- Whether the imported workflow was kept or deleted.

On failure after retries, set `status` to `failed` and report:

- Last failure phase and error.
- Plan changes attempted each attempt.
- What still needs user input (test data, external endpoint, event trigger).

## Cleanup

- After a **verify-only** run when the user does not want to keep artifacts: `delete_workflow` for the `agent-verify-*` import.
- After **pass** and user wants to keep: leave active; tell them how to rename or export.
- Always delete superseded `agent-verify-*` imports from earlier failed attempts in the same session.

## Handoffs

| Situation | Hand off to |
| --- | --- |
| No plan / design gaps | `zuora-workflow-design` |
| Lint/build failures before verify | `zuora-workflow-build` |
| Callout handler code needed | `zuora-api-build` + `/zuora-validate` |
| User wants production promotion | Manual export/import process (out of scope for auto-verify) |

## When invoked from `zuora-workflow-build`

If build just finished with lint exit 0 and the user asked to verify (or said "test in sandbox"), continue into this skill using the artifacts from that build session. Do not re-ask for paths already known — but **still run Step 2e** and obtain explicit confirmation before any `import_workflow` or `run_workflow` call.
