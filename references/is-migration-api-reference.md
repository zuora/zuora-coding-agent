# Credit Memos / Debit Memos Migration: API & Field Reference

This reference provides detailed field-level mappings and API operations for migrating from legacy invoice adjustments to Credit Memos and Debit Memos. Use this when generating code or updating queries.

## Legacy → IS Object Field Mapping

### InvoiceAdjustment → CreditMemoApplication + CreditMemo

| Legacy field | Legacy column | New object | New column | Notes |
|---|---|---|---|---|
| *(id)* | id | CreditMemoApplication | id | Primary key |
| AdjustmentNumber | number | CreditMemo | memo_number | Join to CreditMemo |
| AdjustmentDate | adjustment_date | CreditMemoApplication | effective_date | New field name |
| Amount | amount | CreditMemoApplication | amount | Same semantics |
| ImpactAmount | impact_amount | CreditMemoApplication | amount | Use same field |
| Comments | description | CreditMemo | comments | Join to CreditMemo |
| AccountingCode | accounting_code | — | `CAST(NULL)` | Not available in Credit Memos |
| ReasonCode | reason_code_name | CreditMemo | reason_code_name | Join to CreditMemo |
| AccountId | customer_account_id | CreditMemoApplication | billing_account_id | New field name |
| Status | status | CreditMemo | status | Join to CreditMemo |
| InvoiceId | invoice_id | CreditMemoApplication | invoice_id | Direct mapping |
| CancelledOn | cancelled_on | CreditMemo | cancelled_on | Join to CreditMemo |
| CancelledById | cancelled_by | CreditMemo | cancelled_by | Join to CreditMemo |

---

### InvoiceItemAdjustment → CreditMemoApplicationItem + CreditMemoApplication + CreditMemo

| Legacy field | Legacy column | New object | New column | Notes |
|---|---|---|---|---|
| *(id)* | id | CreditMemoApplicationItem | id | Primary key |
| AdjustmentNumber | number | CreditMemo | memo_number | Join through CreditMemoApplication |
| AdjustmentDate | adjustment_date | CreditMemoApplicationItem | effective_date | New field name |
| Amount | amount | CreditMemoApplicationItem | amount | Direct mapping |
| SourceId (InvoiceItem) | source_id | CreditMemoApplicationItem | invoice_item_id | Separate column |
| SourceId (TaxationItem) | source_id | CreditMemoApplicationItem | invoice_tax_item_id | Separate column |
| Comment | comment | CreditMemo | comments | Join to CreditMemo |
| AccountingCode | accounting_code | — | `CAST(NULL)` | Not available in Credit Memos |
| ReasonCode | reason_code_name | CreditMemo | reason_code_name | Join to CreditMemo |
| Status | status | CreditMemo | status | Join to CreditMemo |
| CancelledById | cancelled_by | CreditMemo | cancelled_by | Join to CreditMemo |
| CancelledDate | cancelled_on | CreditMemo | cancelled_on | Join to CreditMemo |

---

### CreditBalanceAdjustment → CreditMemoApplication + CreditMemo / Payment

| Legacy field | Legacy column | New object | New column | Notes |
|---|---|---|---|---|
| *(id)* | id | CreditMemoApplication | id | Primary key |
| Number | number | CreditMemo | memo_number | Join to CreditMemo |
| AdjustmentDate | adjustment_date | CreditMemoApplication | effective_date | New field name |
| Amount | amount | CreditMemoApplication | amount | Direct mapping |
| Type (Increase/Decrease) | type | — | `CAST(NULL)` | Not available in Credit Memos model |
| SourceTransactionId | source_transaction_id | CreditMemoApplication | source_transaction_id / target_transaction_id | Context-dependent |
| AccountingCode | accounting_code | — | `CAST(NULL)` | Not available in Credit Memos |
| ReasonCode | reason_code_name | CreditMemo | reason_code_name | Join to CreditMemo |
| Status | status | CreditMemo | status | Join to CreditMemo |
| Comment | comment | CreditMemo | comments | Join to CreditMemo |
| CancelledOn | cancelled_on | CreditMemo | cancelled_on | Join to CreditMemo |

**Migration note:** Credit balance adjustments are now modeled as `CreditMemoApplication` records. Over-payments are tracked on the `Payment` object via `unapplied_amount`.

### CreditMemoApplication + CreditMemo (replaces CreditBalanceAdjustment)

| Legacy field | Legacy column | IS source | IS column | Notes |
|---|---|---|---|---|
| *(id)* | id | CreditMemoApplicationDS | id | Primary key |
| Number | number | CreditMemoDS | memo_number | Join to CreditMemo |
| AdjustmentDate | adjustment_date | CreditMemoApplicationDS | effective_date | New field name |
| Amount | amount | CreditMemoApplicationDS | amount | Direct mapping |
| Type (Increase/Decrease) | type | *(no equivalent)* | `CAST(NULL)` | Not available in IS |
| SourceTransactionId | source_transaction_id | CreditMemoApplicationDS | source_transaction_id / target_transaction_id | Context-dependent |
| AccountingCode | accounting_code | *(no equivalent)* | `CAST(NULL)` | Not available in IS |
| ReasonCode | reason_code_name | CreditMemoDS | reason_code_name | Join to CreditMemo |
| Status | status | CreditMemoDS | status | Join to CreditMemo |
| Comment | comment | CreditMemoDS | comments | Join to CreditMemo |
| CancelledOn | cancelled_on | CreditMemoDS | cancelled_on | Join to CreditMemo |

**Migration note:** Credit balance adjustments are now consolidated into `CreditMemoApplication` records. The over-payment is tracked directly on the `Payment` object via `unapplied_amount`.

**IS-specific note:** In Invoice Settlement, **negative charges automatically generate CreditMemo objects during billing**. There is no "negative invoice" in IS. When you bill an account with negative charges, the billing run creates a corresponding CreditMemo instead. You do NOT need to explicitly create CreditMemo objects — they are auto-generated. Your code should query for and apply the auto-generated CreditMemo.

---

### RefundApplication (replaces RefundInvoicePayment)

| Legacy field | Legacy column | IS field | IS column | Notes |
|---|---|---|---|---|
| RefundAmount | refund_amount | ApplyAmount | apply_amount | Renamed |
| RefundId | refund_id | RefundId | refund_id | Direct mapping |
| InvoicePaymentId | payment_invoice_id | *(id)* | id | RefundApplication ID (not InvoicePayment ID) |
| *(none)* | — | PaymentId | payment_id | **NEW:** Direct payment reference |
| *(none)* | — | InvoiceId | invoice_id | **NEW:** Direct invoice reference |
| *(none)* | — | CreditMemoId | credit_memo_id | **NEW:** Credit memo linkage |
| *(none)* | — | EffectiveDate | effective_date | **NEW:** Application date |

**Key change:** RefundApplication eliminates the intermediate `RefundInvoicePayment` join — refunds now link directly to invoices and payments.

---

## REST API Endpoint Mapping

### Credit Memo Operations

| Legacy use case | Legacy operation | IS REST API | Endpoint | Request body |
|---|---|---|---|---|
| Create credit from charge | Negative charge + CB transfer | Create Credit Memo | `POST /v1/creditmemos` | Charge reference (no negative invoice) |
| Create credit from invoice | Adjustment | Create Credit Memo from Invoice | `POST /v1/invoices/{invoiceKey}/creditmemos` | Items and amounts |
| Apply credit | Credit Balance / Create | Apply Credit Memo | `PUT /v1/creditmemos/{creditMemoKey}/apply` | Item-level or invoice-level |
| Refund credit | *(not available)* | Refund Credit Memo | `POST /v1/creditmemos/{creditMemoKey}/refunds` | **NEW:** Direct refund capability |

### Debit Memo Operations

| Legacy use case | Legacy operation | IS REST API | Endpoint | Request body |
|---|---|---|---|---|
| Write off invoice | Invoice Item Adjustment | Write Off Invoice | `PUT /v1/invoices/{invoiceKey}/write-off` | Items and write-off reason |
| Create debit from invoice | Invoice Item Adjustment | Create Debit Memo from Invoice | `POST /v1/invoices/{invoiceKey}/debitmemos` | Items and amounts |
| Reverse invoice | Subscription cancel + manual adjustments | Reverse Invoice | `PUT /v1/invoices/{invoiceKey}/reverse` | Reversal method |

### Invoice Changes

| Operation | Legacy API | IS API | Change |
|---|---|---|---|
| Query invoices | Object Query API | Object Query API | New fields: `credit_memo_applications`, `debit_memo_applications` |
| Generate invoice | Billing run | Billing run | Same endpoint, new related objects |
| Get invoice details | Get Invoice | Get Invoice | New expandable relations (credit memos, debit memos, payment applications) |

---

## Important field naming conventions

- All IS table columns follow `ApiFieldName` → snake_case: `ApplyAmount` → `apply_amount`
- Status fields on IS objects (`credit_memo.status`, `payment.payment_status`) replace legacy snapshot CTEs
- Direct joins are now preferred (no intermediate snapshot tables needed)
- Foreign keys consistently named: `invoice_id`, `payment_id`, `refund_id`, etc.
- Amount fields: always named `amount` or `apply_amount` depending on context


