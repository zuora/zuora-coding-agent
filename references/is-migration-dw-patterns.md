# Invoice Settlement: Data Warehouse Migration Patterns

This reference covers how enabling Invoice Settlement (IS) changes the Zuora data model for downstream data warehouses and BI layers. Use it when customers report DW/BI query breakage or data gaps after IS go-live, or when generating IS-compatible rewrites of their warehouse queries.

---

## Background: Why IS Breaks DW Queries

IS replaces several legacy settlement objects with new ones. Warehouse pipelines that read the legacy objects will miss new IS transactions and may double-count migrated historical records if both old and new tables are read simultaneously.

### Legacy objects retired / replaced by IS

| Legacy object | Replaced by | Notes |
|---|---|---|
| `InvoicePayment` | `PaymentApplication` | IS migration creates a 1:1 `PaymentApplication` for every historical `InvoicePayment`. Legacy records are **not deleted**. |
| `RefundInvoicePayment` | `RefundApplication` | Same pattern — legacy records remain. |
| `CreditBalanceAdjustment` (type: Increase) | `CreditMemo` (unapplied) | Credit balance is migrated to an unapplied CreditMemo. CBA records themselves are not migrated. |
| `CreditBalanceAdjustment` (type: Decrease) | `CreditMemoApplication` | |
| `InvoiceAdjustment` | `CreditMemo` / `DebitMemo` | New adjustments are created as Memos post-IS. |
| `InvoiceItemAdjustment` | `CreditMemoItem` / `DebitMemoItem` | |

### New objects added by IS (no legacy equivalent)

| New object | Purpose |
|---|---|
| `CreditMemo` | Billing document that reduces customer AR (replaces credits/write-offs) |
| `CreditMemoItem` | Line items of a CreditMemo |
| `CreditMemoApplication` | How a CreditMemo is applied to an invoice |
| `DebitMemo` | Billing document that increases customer AR |
| `DebitMemoItem` | Line items of a DebitMemo |
| `PaymentApplication` | How a payment is applied to an invoice (replaces InvoicePayment) |
| `RefundApplication` | How a refund is applied (replaces RefundInvoicePayment) |

---

## Two Sync Modes

Ask the customer which sync mode their DW pipeline uses before producing rewrites.

### Mode A: Incremental Sync

**What it means:** The pipeline processes only new/changed records on each run. Historical data is kept as-is from prior loads.

**IS migration behavior:**
- Legacy records (pre-IS) were loaded historically and remain in the warehouse. Don't re-load them.
- After IS go-live, new records only appear in IS objects (`PaymentApplication`, `CreditMemo`, etc.). Legacy objects no longer receive new rows.
- Existing models that read legacy objects continue to work for historical data — they just stop growing.
- New models must be added for IS objects to capture post-IS activity.
- No deduplication is needed because the pipeline only ever wrote each record once.

**Rewrite strategy:**
- Keep existing models for historical data (they still produce correct rows for pre-IS records).
- Add new sibling models for IS objects.
- Optionally add new models for `CreditMemo` / `DebitMemo` (entirely new documents with no pre-IS equivalent).

### Mode B: Full Historical Sync

**What it means:** Each pipeline run rebuilds the full history from scratch — all records are re-read and re-written every time.

**IS migration behavior:**
- IS migration creates `PaymentApplication` records mirroring every historical `InvoicePayment` (1:1). If both `InvoicePayment` and `PaymentApplication` are UNION ALL'd without deduplication, **every pre-IS payment is counted twice**.
- Same double-count risk for `RefundInvoicePayment` / `RefundApplication`.
- `CreditBalanceAdjustment` records are not migrated — the credit balance is converted to an unapplied CreditMemo, but old CBA rows remain and should still be included (they're not duplicated).

**Rewrite strategy:**
- Use a UNION ALL of legacy + IS tables, with an **anti-join on the legacy table** to exclude IS-migrated records from the IS side.
- The anti-join pattern: include a `PaymentApplication` row only when there is no matching `InvoicePayment` row (i.e., the PA was created after IS go-live, not migrated from IP).

---

## Incremental Sync: SQL Patterns

These patterns follow the constructconnect reference rewrites. The DW tooling in the examples is dbt (using `{{ ref() }}`), but the logic applies to any SQL-based tool — substitute table names appropriate for the customer's environment.

### Pattern 1 — Payment model (InvoicePayment → PaymentApplication)

**Before IS (incremental):**
```sql
-- reads InvoicePayment only
with invoice_payment as (
  select * from stg_zuora__invoice_payment   -- or {{ ref('stg_zuora__invoice_payment') }}
),
-- ... joins to invoice, invoice_item, credit_balance_adjustment ...
select ... from invoice_payment
```

**After IS (incremental):**
```sql
-- replace invoice_payment with payment_application
with payment_application as (
  select * from stg_zuora__payment_application
),
-- retain credit_balance_adjustment only for pre-IS CBA records (not migrated to IS)
credit_balance_adjustment as (
  select * from stg_zuora__credit_balance_adjustment
),
-- ... joins to invoice, invoice_item ...
select ... from payment_application
```

**Key field changes:**
| Legacy field (InvoicePayment) | IS field (PaymentApplication) |
|---|---|
| `invoice_payment_id` | `payment_application_id` |
| `invoice_payment` (join key) | `payment_application` (join key) |
| *(implicit)* | `apply_amount` — amount applied to the invoice |

### Pattern 2 — Refund model (RefundInvoicePayment → RefundApplication)

**Before IS (incremental):**
```sql
with refund_invoice_payment as (
  select * from stg_zuora__refund_invoice_payment
),
...
```

**After IS (incremental):**
```sql
-- IS: refund_application replaces refund_invoice_payment
with refund_application as (
  select * from stg_zuora__refund_application
),
-- IS: credit_balance_adjustment retained for pre-IS CBA records.
-- CB Refund records are NOT migrated to RefundApplication.
credit_balance_adjustment as (
  select * from stg_zuora__credit_balance_adjustment
),
...
```

**Key field changes:**
| Legacy field (RefundInvoicePayment) | IS field (RefundApplication) |
|---|---|
| `refund_invoice_payment_id` | `refund_application_id` |

### Pattern 3 — Invoice model adjustments

**Before IS (incremental):**
```sql
invoice_adjustment as (
  select * from stg_zuora__invoice_adjustment
),
invoice_item_adjustment as (
  select * from stg_zuora__invoice_item_adjustment
),
credit_balance_adjustment as (
  select * from stg_zuora__credit_balance_adjustment
),
```

**After IS (incremental):**
```sql
-- IS: IIA/IA/CBA legacy objects remain unchanged — these records are not migrated to IS objects.
-- IS migration migrates CreditBalance (the balance, not CBAs) to an unapplied CreditMemo.
-- New IS activity (CreditMemo/DebitMemo) is tracked in separate dedicated models.
invoice_adjustment as (
  select * from stg_zuora__invoice_adjustment   -- keep for historical pre-IS records
),
invoice_item_adjustment as (
  select * from stg_zuora__invoice_item_adjustment   -- keep for historical pre-IS records
),
credit_balance_adjustment as (
  select * from stg_zuora__credit_balance_adjustment   -- keep; not migrated to IS
),
-- Add new models for IS activity:
-- credit_memo / credit_memo_item  → in dim_transactions_creditmemo_is
-- debit_memo  / debit_memo_item   → in dim_transactions_debitmemo_is
```

### Pattern 4 — CreditMemo model (entirely new — incremental)

```sql
-- IS: CreditMemo is a new billing document with no legacy equivalent.
-- Sign convention: non-canceled rows have negative transaction_amount (reduces AR).
with credit_memo as (
  select * from stg_zuora__credit_memo
),
credit_memo_item as (
  select * from stg_zuora__credit_memo_item
),
-- join to subscription / product dimension for enrichment if needed
...
select
  credit_memo_item_id      as transaction_id,
  credit_memo_id,
  'CreditMemoItem'         as transaction_type,
  amount * -1              as transaction_amount,   -- negative = reduces AR
  ...
from credit_memo_item
join credit_memo using (credit_memo_id)
```

### Pattern 5 — DebitMemo model (entirely new — incremental)

```sql
-- IS: DebitMemo increases customer AR (opposite of CreditMemo).
-- Sign convention: non-canceled rows have positive transaction_amount.
with debit_memo as (
  select * from stg_zuora__debit_memo
),
debit_memo_item as (
  select * from stg_zuora__debit_memo_item
),
...
select
  debit_memo_item_id       as transaction_id,
  debit_memo_id,
  'DebitMemoItem'          as transaction_type,
  amount                   as transaction_amount,   -- positive = increases AR
  ...
from debit_memo_item
join debit_memo using (debit_memo_id)
```

---

## Full Historical Sync: SQL Patterns

For full-sync pipelines, the critical requirement is deduplication when unioning legacy and IS tables. IS migration creates IS records mirroring every legacy record — without deduplication you double-count.

### Pattern 6 — Payment union with deduplication (full sync)

```sql
-- IS migration creates a PaymentApplication for every historical InvoicePayment (1:1),
-- but does NOT delete the original InvoicePayment record. Union without dedup = double-count.
--
-- Fix: is_rows uses an anti-join on (payment_id, invoice_id) to include ONLY
-- PaymentApplication records that have no matching InvoicePayment —
-- i.e., genuinely new records created after IS go-live.

with invoice_payment as (
  select * from stg_zuora__invoice_payment
),
payment_application as (
  select * from stg_zuora__payment_application
),

legacy_rows as (
  -- all pre-IS invoice payments
  select
    invoice_payment_id  as payment_record_id,
    payment_id,
    invoice_id,
    amount,
    'InvoicePayment'    as source_object,
    created_date,
    updated_date
  from invoice_payment
),

is_rows as (
  -- only PaymentApplications that have no matching InvoicePayment (post-IS)
  select
    pa.payment_application_id  as payment_record_id,
    pa.payment_id,
    pa.invoice_id,
    pa.apply_amount            as amount,
    'PaymentApplication'       as source_object,
    pa.created_date,
    pa.updated_date
  from payment_application pa
  left join invoice_payment ip
    on ip.payment_id = pa.payment_id
    and ip.invoice_id = pa.invoice_id
  where ip.invoice_payment_id is null          -- exclude IS-migrated PAs
    and pa.invoice_id is not null              -- invoice-linked only
    and pa.payment_application_status = 'Processed'
),

final as (
  select * from legacy_rows
  union all
  select * from is_rows
)

select * from final
```

### Pattern 7 — Refund union with deduplication (full sync)

```sql
-- Same deduplication pattern for refunds.
-- RefundApplication has no status column per HBM — no status filter on RA side.

with refund_invoice_payment as (
  select * from stg_zuora__refund_invoice_payment
),
refund_application as (
  select * from stg_zuora__refund_application
),

legacy_rows as (
  select
    refund_invoice_payment_id  as refund_record_id,
    refund_id,
    invoice_id,
    amount,
    'RefundInvoicePayment'     as source_object,
    created_date,
    updated_date
  from refund_invoice_payment
),

is_rows as (
  -- only RefundApplications without a matching RefundInvoicePayment
  select
    ra.refund_application_id   as refund_record_id,
    ra.refund_id,
    ra.invoice_id,
    ra.apply_amount            as amount,
    'RefundApplication'        as source_object,
    ra.created_date,
    ra.updated_date
  from refund_application ra
  left join refund_invoice_payment rip
    on rip.refund_id = ra.refund_id
    and rip.invoice_id = ra.invoice_id
  where rip.refund_invoice_payment_id is null
    and ra.invoice_id is not null
),

final as (
  select * from legacy_rows
  union all
  select * from is_rows
)

select * from final
```

### Pattern 8 — CreditBalanceAdjustment (full sync — no IS equivalent)

```sql
-- CBA Increase ("Transfer Negative Invoice → Credit Balance") and CB Payment
-- (overpayment creating credit balance) have no direct IS row-level equivalent.
--
-- In IS, these are represented by:
--   - Payment.unapplied_amount (for CB Payment — overpayment)
--   - CreditMemo creation (for CB Increase — negative invoice transfer)
--
-- Since these are state fields rather than transaction rows, no union/dedup needed.
-- Keep reading CreditBalanceAdjustment as-is; it was NOT migrated to IS objects.

with credit_balance_adjustment as (
  select * from stg_zuora__credit_balance_adjustment
),
...
-- no IS equivalent to union in — CBA records stand alone
select * from credit_balance_adjustment
```

---

## Staging Model Naming Conventions

The patterns above use the `stg_zuora__<object>` naming convention. Substitute the customer's actual table/view names:

| Conceptual object | dbt staging ref | Fivetran / raw SQL typical name |
|---|---|---|
| InvoicePayment | `stg_zuora__invoice_payment` | `zuora.invoice_payment` |
| PaymentApplication | `stg_zuora__payment_application` | `zuora.payment_application` |
| RefundInvoicePayment | `stg_zuora__refund_invoice_payment` | `zuora.refund_invoice_payment` |
| RefundApplication | `stg_zuora__refund_application` | `zuora.refund_application` |
| CreditBalanceAdjustment | `stg_zuora__credit_balance_adjustment` | `zuora.credit_balance_adjustment` |
| InvoiceAdjustment | `stg_zuora__invoice_adjustment` | `zuora.invoice_adjustment` |
| InvoiceItemAdjustment | `stg_zuora__invoice_item_adjustment` | `zuora.invoice_item_adjustment` |
| CreditMemo | `stg_zuora__credit_memo` | `zuora.credit_memo` |
| CreditMemoItem | `stg_zuora__credit_memo_item` | `zuora.credit_memo_item` |
| CreditMemoApplication | `stg_zuora__credit_memo_application` | `zuora.credit_memo_application` |
| DebitMemo | `stg_zuora__debit_memo` | `zuora.debit_memo` |
| DebitMemoItem | `stg_zuora__debit_memo_item` | `zuora.debit_memo_item` |
| PaymentApplicationItem | `stg_zuora__payment_application_item` | `zuora.payment_application_item` |

---

## Key Pitfalls

1. **Double-counting migrated records (full sync only):** IS migration creates PA/RA rows mirroring every legacy IP/RIP row. In full sync mode, union both tables without the anti-join dedup and every pre-IS payment is counted twice. Always use Pattern 6/7 when operating in full sync mode.

2. **CBA records are NOT migrated:** `CreditBalanceAdjustment` rows are left in place. The credit *balance* is converted to an unapplied CreditMemo, but the CBA transaction rows remain unchanged. Continue reading the CBA table for historical transactions.

3. **CreditMemo and DebitMemo are net-new:** There are no legacy rows for these objects. You must add new models — they are not covered by updating existing models.

4. **Sign convention:** CreditMemo items are typically recorded with a *negative* `amount` (reduces AR). DebitMemo items are positive. Confirm sign conventions with the customer's AR/finance team before finalizing.

5. **Staging model availability:** Before writing SQL, confirm the customer's DW pipeline actually syncs the new IS objects (`payment_application`, `credit_memo`, `debit_memo`, etc.) from Zuora. If using Fivetran/HVR, these tables may need to be explicitly enabled.

6. **RefundApplication has no `status` column:** Unlike `PaymentApplication` (which has `payment_application_status`), `RefundApplication` has no status field in the Zuora HBM. Do not add a status filter on the RA side.

---

## DW Rewrite Checklist

- [ ] Identify all DW models/queries that reference legacy settlement objects
- [ ] Confirm DW pipeline syncs IS objects (`payment_application`, `credit_memo`, `debit_memo`, etc.)
- [ ] Determine sync mode (incremental vs full historical)
- [ ] For **incremental**: add new IS models alongside existing legacy models
- [ ] For **full sync**: apply anti-join deduplication pattern on payment and refund unions
- [ ] Add new `dim_transactions_creditmemo` and `dim_transactions_debitmemo` models
- [ ] Validate staging model field names match customer's DW schema
- [ ] Run end-to-end reconciliation: compare IS-rewritten output vs legacy output for overlapping data
- [ ] Confirm no records are lost or double-counted for the historical period

---

## References

- [Invoice Settlement Overview](https://docs.zuora.com/en/zuora-billing/bill-your-customer/invoice-settlement/get-started-with-invoice-settlement/invoice-settlement-overview)
- [IS Migration Checklist and Guide](https://docs.zuora.com/en/zuora-billing/bill-your-customer/invoice-settlement/get-started-with-invoice-settlement/invoice-settlement-migration-checklist-and-guide)
- `${CLAUDE_PLUGIN_ROOT}/references/is-migration-api-reference.md` — legacy→IS field mapping
- `${CLAUDE_PLUGIN_ROOT}/references/is-migration-patterns.md` — API migration patterns
