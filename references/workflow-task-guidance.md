# Workflow task guidance

Behavioral rules for each `action_type` — **when to use it**, **how to configure it**, and **common mistakes**. For JSON shape and `required_at_import`, use `workflow-task-templates.json` and `workflow-task-configuration.md`. For task selection across types, read `workflow-data-retrieval.md` first.

Before emitting fields or `where_clause` predicates, run describe (build skill Step 3a) or use `references/zuora-standard-fields.json`.

---

## Query

**Results:** `Data.<object>[]` (array, max **2000** rows; task fails if exactly 2000 returned).

**Limitations:** single object; no JOINs; no ORDER BY; no GROUP BY; no relative dates; SOAP context only (some objects like certain billing-document types may be export-only — confirm via describe).

**Prefer Query when:**

1. Specific record by ID from event or prior task.
2. **REALTIME / UIACTION** workflows (Export unavailable).
3. **Per-parent child lookup inside `Iterate`** (e.g. `InvoiceItem WHERE InvoiceId = '{{ Data.Invoice.Id }}'`).
4. Small enrichment fetch (Account fields not in event payload).
5. Count guaranteed &lt; 2000.

**Use something else when:** run results / unknown volume → `Export`; SQL JOINs → `Data::Link`; nested single record → `GraphQuery`; bulk custom objects → `CustomObject::Query`.

**Config:** `parameters.fields[<object>][<Field>] = "true"` (object-keyed, not comma string). `zero_query_proceed` defaults false (true only when downstream must run on empty results).

**Never:** `Query Invoice` scoped to a bill run after `BillingRunCompletion` (`W196`) — use `Export` with `Invoice.SourceId = '{{ Data.BillingRun.ID }}'`. Do not use `BillRunId` in `where_clause` (`W197`).

---

## Export

**Results:** CSV file in `Data.Files.*`; row fields as `Data.<object>.<field>` only inside downstream `Iterate`.

**Capabilities Query lacks:** unlimited rows; ORDER BY; GROUP BY + HAVING; aggregates (Sum, Count, Max, Min, Average); relative dates; 1:1/N:1 multi-object `fields`.

**BATCH only** — not available in REALTIME / UIACTION.

**Prefer Export when:**

1. Polling / unknown volume.
2. **Run-completion results** (`BillingRunCompletion`, `PaymentRunCompletion`, `JournalRunCompletion`).
3. Reporting, sorting, time-window queries.
4. Bulk processing without specific IDs.

**Join on export:** add related 1:1/N:1 objects under **separate keys** in `parameters.fields` (see `workflow-data-retrieval.md`). Downstream: `{{ Data.Account.Name }}`, not nested under Invoice.

**Config:** `parameters.fields[<Object>][<Field>] = "true" | "Sum" | "Count" | …`. `where_clause` order: filter, GROUP BY, HAVING, ORDER BY, LIMIT. `zip` default `"true"` → `Invoice__<taskId>.csv.zip`. `zero_result_stop` default false unless downstream must run empty.

**Iterate.object** after Export = file holder name, not bare object (`E176`).

---

## Data::Link

**Results:** SQL-style rows in `Data.*` or async CSV file (depending on mode).

**Prefer when:** multi-table JOINs, complex SQL aggregations, denormalized reporting, run results needing joined columns in one query.

**Do not** use a JOIN to fetch parent + 1:N children in one step — use Export → Iterate → Query pattern instead.

**Config:** `parameters.query` — Trino SQL with Liquid. Consolidate scalar lookups with CTE + `CROSS JOIN` (`W180`).

---

## GraphQuery

**Results:** nested `Data.<baseObject>` structure.

**Prefer when:** single record with nested related objects; collections &lt; 200 each.

**Not for:** bulk data, aggregations, or large related collections.

---

## Iterate

**Scoping task** — rebinds `Data.<object>` to one row inside `For Each`.

**`object` values:**

| Upstream | `Iterate.object` |
| --- | --- |
| `Export` / `Data::Link` file | `Invoice__<taskId>.csv.zip` (or `.csv`) |
| `Query` / `GraphQuery` | Object name (`Invoice`) |
| Custom collection | `CUSTOM LIQUID` + `liquid_statement` |

One `For Each` linkage to first inner task; no link back to Iterate. Use `Complete` for after-loop convergence.

Inside loop: `Data.Invoice.Id`, not `Data.Invoice[0].Id` (`W173`).

---

## Logic::Liquid

**Results:** `Data.Liquid.<name>` (or `Data.<placement>.<name>`) per `{% assign %}` / `{% capture %}`.

**Prefer built-in filters** (`where`, `where_exp`, `group_by`) over manual `for`/`if`/`push` (`W184`).

**Do not** add a standalone Liquid task when output is consumed by only the next task — inline into that task's parameter (`W187`). See `workflow-patterns.md` → Inline Liquid in consuming tasks.

**Do not** reference `Data.Liquid.*` inside the same Liquid task's code.

---

## If / Logic::Case

Branch on Liquid boolean / case expressions. Inline conditions here instead of a separate Liquid assign-only task.

---

## Callout / AsynchronousCallout

**Zuora API:** `authorization.type = "zuora"` (`E186`); `validation.zuora_call = "true"` (`W190`).

**External API:** `authorization.type` per saved provider or `"none"` with appropriate headers.

**Body:** author `parameters.raw_body` directly with Liquid — no one-consumer Liquid shim (`W187`). For arrays, prefer upstream `Query` + `| to_json` over large `{% for %}` blocks when possible.

**Async:** `AsynchronousCallout` needs `polling_url`, `finish_status`, `response_path`; poll before dependent async work (`W195`).

---

## Email

Liquid in `parameters.email` (`to`, `subject`, `body`). Inline template content; avoid Liquid-only predecessor task (`W187`).

---

## Create / Update / Delete

SOAP CRUD. `parameters.fields[<object>][<Field>]`. Consolidate multiple field updates on same `object_id` into one `Update` (`W183`).

---

## CustomObject::*

Only when user explicitly requests custom objects (`W194`). Shape: `object` without trailing `__c` (`E187`); nested `fields[<object>]` (`E188`).

---

## Billing::BillRun

OOTB task for standard bill-run modes (`single`, `adhoc`, `replicate`). Unsupported filters (account-number, batch-number, APM/PRPC) → Zuora `Callout` to `{{ Credentials.zuora.rest_endpoint }}bill-runs` (`W185`). Do not use legacy `/object/bill-run` (`W192`).

Async create → poll before dependent work (`W195`).

---

## Payment::PaymentRun

Create/update/get/delete payment runs. Run-completion payment exports follow same **Export not Query** rule as bill runs — confirm run filter via describe.

---

## Billing::BillRun / Payment::PaymentRun / journal runs (async)

Treat create `Success` as job-submitted only. Poll status before posting or chaining another async operation.

---

## Related files

- `workflow-data-retrieval.md` — which task to pick
- `workflow-planning-patterns.md` — named flows (run_event, callout, …)
- `workflow-task-templates.json` — exact JSON templates
- `workflow-task-configuration.md` — parameter contracts
