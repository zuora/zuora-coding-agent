# Workflow data retrieval decision matrix

Choose the data-fetching `action_type` from the **use-case pattern**, not habit. Query and Export both use ZOQL syntax but are different engines with different limits.

| Feature | `Query` | `Export` | `Data::Link` / Data Query | `GraphQuery` |
| --- | --- | --- | --- | --- |
| Syntax | ZOQL (SOAP) | ZOQL (AQuA export) | Trino SQL | GraphQL |
| JOINs | No | 1:1 / N:1 via multi-object `fields` | Full SQL JOINs | Nested hierarchy |
| ORDER BY | No | Yes | Yes | N/A |
| GROUP BY / aggregates | No | Yes (Sum, Count, Max, Min, Average) | Yes | No |
| Relative dates (`today - 30 days`) | No | Yes | Limited | N/A |
| Record limit | **2000 hard cap** | Unlimited (file) | Large (async file) | 200 per related collection |
| REALTIME / UIACTION | Yes | **No** (BATCH only) | BATCH / async | Yes |
| Result shape | `Data.<object>[]` | CSV file → `Iterate` | Rows in `Data.*` or file | Nested `Data.<baseObject>` |

See also: `workflow-task-catalog.md` → Data-read selection guide, `workflow-task-guidance.md` → per-task sections.

## Decision matrix by pattern

| Use-case pattern | Task | Notes |
| --- | --- | --- |
| Specific record by ID, count guaranteed &lt; 2000 | `Query` | Safe in REALTIME / UIACTION workflows |
| Per-record child lookup inside `Iterate` | `Query` | e.g. `InvoiceItem WHERE InvoiceId = '{{ Data.Invoice.Id }}'` — child count per parent is usually &lt; 2000 |
| Enrichment in REALTIME (fields not in event payload) | `Query` | e.g. `Query Account` by `{{ Data.Invoice.AccountId }}` before Email/Callout |
| Polling / unknown volume ("get all X", "recent X") | `Export` | Supports ORDER BY and relative dates |
| **Run results** (bill / payment / journal run completion) | **`Export`** (or `Data::Link` if SQL JOIN needed) | Runs routinely produce **&gt; 2000** rows — **never `Query` for the parent collection**. Linter `W196` flags `Query Invoice` scoped to a bill run. |
| Reporting / analytics (GROUP BY, SUM, COUNT) | `Export` | `Query` has no GROUP BY / HAVING |
| Sorted results | `Export` | `Query` has no ORDER BY |
| Time-based ("last 30 days") | `Export` | Relative dates must be quoted: `'today - 30 days'` |
| Multi-object flat JOIN | `Data::Link` | When ZOQL field paths are not enough |
| Nested single-record hierarchy | `GraphQuery` | Account → Subscriptions → RatePlans in one call |
| Custom object | `CustomObject::Query` | Not in ZOQL / Data::Link |
| Billing preview | `Data::BillingPreviewRun` | Dedicated preview endpoint |

## Call-type rules (event-triggered workflows)

| Event class | `call_type` | Data-read pattern |
| --- | --- | --- |
| Run completion: `BillingRunCompletion`, `PaymentRunCompletion`, `JournalRunCompletion` | **BATCH** | `Export` → `Iterate` (or `Data::Link` when JOINs required) |
| Per-record: `InvoicePosted`, `PaymentProcessed`, `SubscriptionCreated`, … | **REALTIME** | Event payload often sufficient; use `Query` only for extra fields |

Do not use BATCH + Export/Iterate for per-record events, or REALTIME + Export for run-completion events.

## Parent + children pattern (Export → Iterate → Query)

When you need parent records **with** 1:N children, do **not** use a single `Data::Link` JOIN — it multiplies parent rows.

1. **`Export`** the parent object (filter by run id, date window, etc.).
2. Pull every **1:1 / N:1** related object on the **same Export** via multi-object `parameters.fields` (see below).
3. **`Iterate`** over the export file holder.
4. **`Query`** only **1:N** child objects inside the loop (e.g. `InvoiceItem` by `InvoiceId`).
5. Action task (`Callout`, `Email`, …) with parent + child data in scope.

### Join on the upstream Export (critical)

`Export` supports ZOQL field paths for 1:1 / N:1 relationships. Add related objects under **their own keys** in `parameters.fields` so the Iterate body gets `Data.Account.*`, `Data.BillToContact.*`, etc. without inner Queries.

**Rule of thumb:** does the relationship multiply rows for the base object?

- **No** (1:1 / N:1) → add fields on the upstream `Export` (Invoice→Account, Invoice→BillToContact, Subscription→Account).
- **Yes** (1:N) → separate task inside the loop (Invoice→InvoiceItem, Account→Subscription).

**Anti-pattern:**

```text
Export Invoice → Iterate → Query Account → Query BillToContact → Query InvoiceItem → Callout
```

**Preferred:**

```text
Export Invoice (Account + BillToContact on same Export) → Iterate → Query InvoiceItem → Callout
```

Example `parameters.fields` shape:

```json
{
  "fields": {
    "Invoice": { "Id": "true", "InvoiceNumber": "true", "Amount": "true", "Status": "true" },
    "Account": { "Id": "true", "Name": "true", "AccountNumber": "true" },
    "BillToContact": { "FirstName": "true", "LastName": "true", "WorkEmail": "true" }
  },
  "where_clause": "Invoice.SourceId = '{{ Data.BillingRun.ID }}'"
}
```

**Field key placement:** each field belongs under the object that **owns** it in describe. Do not put `AccountNumber` or `WorkEmail` under `Invoice`. Downstream Liquid uses flat paths: `{{ Data.Account.AccountNumber }}`, not `{{ Data.Invoice.Account.AccountNumber }}`.

**Run-scoping filter (bill-run invoices):** use **`Invoice.SourceId = '{{ Data.BillingRun.ID }}'`**, not `BillRunId`. `Invoice.BillRunId` exists in describe but is **`filterable=false`** — Object Query/Export rejects it at runtime (*"There is no field named BillRunId."*). `Invoice.SourceId` is filterable and holds the bill-run id when `Source = 'BillRun'`. For payment-run and journal-run exports, confirm the run-scoping field via describe (`SourceId` or tenant-specific equivalent). Linter `W197` warns on `BillRunId` in `where_clause`.

Do not include non-exportable FK columns (e.g. `AccountId`) under `Invoice` when the related object block already provides the data.

Inside `Iterate`, `Data.Account.*` and `Data.BillToContact.*` are already populated from the Export.

## Decision examples

**BATCH (run events):**

- "When bill run completes, POST each invoice to ERP" → `Export Invoice` (run filter) → `Iterate` → `Query InvoiceItem` → `Callout`.
- "Invoices from bill run with account details in one flat file" → `Data::Link` (SQL JOIN) **or** `Export` with Account fields on the same export.

**REALTIME (per-record events):**

- "When invoice is posted, email customer" → often just `Email` (payload has `BillToContact.WorkEmail`).
- "When subscription is created, provision externally" → `Query Subscription` → `Callout`.

**General:**

- "Get all overdue invoices" → `Export` (unknown volume).
- "Get invoice by ID from trigger" → `Query`.
- "Count invoices by status" → `Export` with GROUP BY.

## When `Query` is wrong

- `Query Invoice WHERE Invoice.SourceId = '{{ Data.BillingRun.ID }}' …` after `BillingRunCompletion` — use `Export` (`W196`). Do not filter by `BillRunId` — not filterable (`W197`).
- `Query` for polling ("all invoices updated since …") — use `Export` with relative dates.
- `Query` when you need ORDER BY or GROUP BY — use `Export` or `Data::Link`.
- `Export` in a REALTIME / UIACTION workflow — use `Query` or `GraphQuery` instead.

## Related files

- `workflow-planning-patterns.md` → `run_event`, `realtime_event`
- `workflow-patterns.md` → Bill run completion → external system
- `workflow-task-guidance.md` → `Query`, `Export`, `Data::Link`, `Iterate`
