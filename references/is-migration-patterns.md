# Invoice Settlement (IS) Migration Patterns

## Credit Memos / Debit Memos Migration

### Overview

Credit Memos and Debit Memos migration moves a tenant from legacy invoice adjustments (InvoiceAdjustment, InvoiceItemAdjustment, CreditBalanceAdjustment) to the modern Credit Memo and Debit Memo models, which provide unified handling of credits and write-offs.

## Object migration map

Credit Memos and Debit Memos migration focuses on adjustment-related objects. Payment and Refund APIs are backward compatible and do NOT require changes.

| Legacy object | New replacement | Migration required |
|---|---|---|
| `InvoiceAdjustment` | `CreditMemoApplication` + `CreditMemo` | **YES** — Update code |
| `InvoiceItemAdjustment` | `CreditMemoApplicationItem` + `CreditMemoApplication` + `CreditMemo` | **YES** — Update code |
| `CreditBalanceAdjustment` | `CreditMemoApplication` + `CreditMemo` | **YES** — Update code |
| `InvoicePayment` | (no change) | NO — Keep existing |
| `RefundInvoicePayment` | (no change) | NO — Keep existing |

**Reference:** See `is-migration-api-reference.md` for detailed field-level mappings and API operations.

### Legacy adjustment API changes

Only invoice adjustment operations require updates. Replace legacy adjustment APIs with Credit Memo equivalents:

| Legacy operation | Legacy SOAP | New REST API endpoint | Migration action |
|---|---|---|---|
| Create invoice adjustment | InvoiceAdjustment / Create | `POST /v1/creditmemos` | Update code to use CreditMemo API |
| Create invoice item adjustment | InvoiceItemAdjustment / Create | `POST /v1/creditmemos/{id}/items` | Update code to use CreditMemoApplicationItem |
| Create credit balance adjustment | CreditBalanceAdjustment / Create | `POST /v1/creditmemos` + `PUT /v1/creditmemos/{id}/apply` | Update code to use CreditMemo + CreditMemoApplication |

**Important:** Payment and Refund APIs are backward compatible. Do NOT change existing payment/refund code.

## Migration phases

1. **Assessment**: Analyze current tenant state — usage of InvoiceAdjustment, InvoiceItemAdjustment, CreditBalanceAdjustment; payment application patterns; custom integrations
2. **Preparation**: Test Credit Memo / Debit Memo support in sandbox; understand new object model and API
3. **Code inventory**: Identify custom queries and code using legacy adjustment objects (see reference for field mappings)
4. **Code refactoring**: Replace SOAP adjustment APIs with REST Credit Memo/Debit Memo equivalents
   - Modify existing methods to use new APIs (do NOT create parallel new methods)
   - Use Zuora SDK (`com.zuora.model.*` and specific API classes like CreditmemosApi)
   - Update integration tests to verify new behavior
   - Remove or deprecate SOAP adjustment service methods once REST equivalents are complete
5. **Validation**: Verify adjustment behavior matches legacy semantics under Credit Memos model; test edge cases
6. **Integration updates**: Update downstream systems to consume Credit Memo / Debit Memo objects instead of legacy adjustments
7. **Production cutover**: Roll out updated code after sandbox validation

## Join relationship changes

**Payment Application** (replaces `InvoicePayment`):
```
Legacy: payment → invoice_payment (payment_id) → invoice (invoice_id)
IS:     payment → payment_application (payment_id) → invoice (invoice_id)
```

**Refund Application** (replaces `RefundInvoicePayment`):
```
Legacy: refund → refund_invoice_payment (refund_id)
       → invoice_payment (invoice_payment_id) → invoice → payment
IS:     refund → refund_application (refund_id) → invoice → payment
```

**Credit Memo Application** (replaces Invoice/Item/CBA Adjustments):
```
IS (invoice-level):
  credit_memo_application → credit_memo (source_transaction_id)
                          → invoice (target_transaction_id)

IS (line-item level):
  credit_memo_application_item → credit_memo_application → credit_memo
                               → invoice → invoice_item
                               → invoice_tax_item
```

## Key considerations

- IS enablement is **irreversible** — validate thoroughly in sandbox first
- Credit balance conversion must account for all outstanding balances
- Payment application now supports invoice-item-level granularity
- API version must be **211.0+** for IS-aware endpoints
- Custom reports and integrations must be updated for new object types
- Status fields (`credit_memo.status`, `payment.payment_status`) replace legacy snapshot CTEs
- Billing documents now include credit memos and debit memos alongside invoices

## Validation checklist

- All credit balances converted and reconciled
- New billing documents generate correctly (invoices, credit memos, debit memos)
- Payment application follows IS rules (including item-level granularity)
- Existing integrations handle new document types
- Reports reflect IS billing model
- Dunning processes work with IS documents
- Revenue recognition unaffected by migration
- API version 211.0+ confirmed on tenant
