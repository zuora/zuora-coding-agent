# Workflow planning patterns

Named composition patterns for `/zuora-workflow-design` and `/zuora-workflow-build`. Pair with `workflow-data-retrieval.md` for task-type choice and `workflow-task-guidance.md` for per-task parameters.

## run_event — run-completion trigger

**When:** Process records created by a billing, payment, or journal run (`BillingRunCompletion`, `PaymentRunCompletion`, `JournalRunCompletion`).

**Steps:**

1. `workflow.event_trigger: true`; set `parameters.event_triggers[]` to the canonical event name (see `workflow-events.md` corrections table).
2. `call_type: BATCH` — run events produce large datasets.
3. Bind run id in `event_parameters` (e.g. `{ object: "BillingRun", key: "ID", value: "<BillRun.ID>" }` → `Data.BillingRun.ID`).
4. First data task **must be `Export`** (or `Data::Link` when SQL JOINs are required) — **not `Query`**. Runs routinely exceed 2000 rows.
5. Filter the export with `Invoice.SourceId = '{{ Data.BillingRun.ID }}'` on `Invoice` (not `BillRunId` — not filterable in Object Query/Export).
6. Pull 1:1 / N:1 related objects on the **same Export** (`Account`, `BillToContact`, …) — see `workflow-data-retrieval.md` → Join on the upstream Export.
7. `Iterate` over the export file holder (`Invoice__<ExportTaskId>.csv.zip`).
8. Inside the loop, `Query` **only** 1:N children (e.g. `InvoiceItem WHERE InvoiceId = '{{ Data.Invoice.Id }}'`).
9. `Callout` / `Email` — inline payload Liquid in `raw_body` / template (`W187`).

**Example:**

```text
BillingRunCompletion
  → Export Invoice (SourceId filter; Account + BillToContact on same export)
  → Iterate
      → Query InvoiceItem
      → Callout POST
```

**Do not:** Notification → Callout bridge when `BillingRunCompletion` is available; `Query Invoice` scoped to a bill run (`W196`); invented scopes like `Data.BillRun.*` or `Data.CurrentInvoice.*`.

See `workflow-patterns.md` for the canonical bill-run → external system pattern.

---

## realtime_event — per-record trigger

**When:** One record per firing (`InvoicePosted`, `PaymentProcessed`, `SubscriptionCreated`, `CreditMemoPosted`, `UpcomingRenewal`, …).

**Steps:**

1. `event_trigger: true` with the single canonical event name.
2. `call_type: REALTIME` (not BATCH).
3. Event payload is available as `Data.<Object>.*` (plus related payload objects — see `workflow-events.md`).
4. If the payload has everything needed (e.g. `InvoicePosted` → Email to `Data.BillToContact.WorkEmail`), go straight to the action — **no Export/Iterate**.
5. If extra fields are needed, use **`Query`** by id from the payload — one record is always &lt; 2000 and `Query` works in REALTIME.

**Examples:**

- `InvoicePosted` → `Email` (fields from event payload).
- `SubscriptionCreated` → `Query Subscription` → `Callout` to provisioning system.

---

## iterate — looping over a collection

**When:** Run a sub-flow for each row from `Query`, `Export`, `GraphQuery`, `Data::Link`, or `Data::Aqua`.

**Steps:**

1. Upstream task produces the collection (file or array).
2. `Iterate.object`:
   - After **`Export` / `Data::Link` / `Data::Aqua`**: file holder name (`Invoice__101.csv.zip`) — **not** bare `Invoice` (`E176`).
   - After **`Query` / `GraphQuery`**: object name (`Invoice`).
3. Link predecessor `Success` → `Iterate`; per-record children use linkage `For Each`; after-loop uses `Complete`.
4. Inside the loop: `Data.<Object>.<Field>` (single row) — not `Data.Invoice[0].Id` (`W173`).

---

## callout — external or Zuora REST integration

**When:** (1) Zuora REST with no dedicated task type (Orders API, bill-run post, invoice email). (2) External webhook / ERP / partner API.

**Steps:**

1. `Callout` (sync) or `AsynchronousCallout` (poll until complete).
2. `parameters.url`, `method`, `authorization` (`type: "zuora"` for Zuora APIs — `E186`).
3. For Zuora API callouts: `validation.replace = "true"`, `validation.zuora_call = "true"` (`W190`); read response via `Data.<scope>.ResponseBody.*` unless `include_response_code = "false"`.
4. **Inline the request body** in `parameters.raw_body` — do not add a one-consumer `Logic::Liquid` shim before Callout (`W187`). Use `{{ Data.Invoice.Id }}`, `{{ Data.InvoiceItem | to_json }}`, etc.
5. Quote Liquid strings in JSON; leave numbers/booleans unquoted. Use `{% for %}` in `raw_body` only when a Query upstream populated an array scope; prefer `Query InvoiceItem` + `| to_json` over inventing `Data.InvoiceItems`.

---

## email — notification

**When:** A recipient email is in scope (`Data.BillToContact.WorkEmail`, `Data.Account.*`, or literal).

**Steps:**

1. Confirm recipient is available (event payload or upstream `Query`/`Export`).
2. Set `parameters.email` with `to`, `from`, `subject`, `body` — all support Liquid.
3. Inline dynamic content in subject/body; avoid a separate `Logic::Liquid` task used only by this Email (`W187`).

---

## parent_child_filter — child by parent FK

**When:** List child records for a parent already in scope (`InvoiceItem` for `Invoice`, `Contact` for `Account`, …).

**Steps:**

1. Confirm FK field name via describe (`InvoiceId`, `AccountId`, …).
2. Child `Query` or `Export` `where_clause`: `<FK> = '{{ Data.<Parent>.Id }}'`.
3. Inside `Iterate` over parents, per-parent child `Query` is the usual pattern when cardinality is 1:N.

---

## consolidated_data_query — scalar context in one SQL query

**When:** You need a row set plus scalar lookup (e.g. run-prompt id → `ProductRatePlanId`).

**Steps:**

1. Prefer **one** `Data::Link` with CTE + `CROSS JOIN`, projecting scalar columns on every row.
2. Do **not** chain `Data::Link → Logic::Liquid(assign only) → Data::Link` (`W180`).
3. Downstream `Iterate` / `Callout` reads `row.<field>` from the single query result.

See `workflow-patterns.md` → Consolidated Data Query With Scalar Context.

---

## Related files

- `workflow-data-retrieval.md` — Query vs Export vs Data::Link matrix
- `workflow-events.md` — event names and `event_parameters`
- `workflow-triggers-and-linkages.md` — trigger flags and linkage types
- `workflow-examples.md` — lint-clean full workflows
