# Order Migration Patterns (Legacy APIs to Order API)

## Overview

Order migration moves subscription management from legacy APIs (Subscription/Amendment CRUD API and Subscribe Action API) to the Order API, which provides a unified, action-based model for subscription changes.

## Migration phases

1. **Assessment**: Inventory existing subscriptions, amendments, custom fields, and integration points
2. **Mapping**: Map legacy operations to Order API actions
3. **Code migration**: Rewrite subscription management code to use Order API
4. **Data migration**: Migrate existing subscriptions to be Order-managed (if needed)
5. **Validation**: Verify subscription state, billing behavior, and reporting
6. **Parallel run**: Run both APIs side-by-side during transition (if feasible)
7. **Cutover**: Switch to Order API exclusively

## Legacy-to-Order API mapping

### Subscription/Amendment API

| Legacy operation | Order API equivalent |
|---|---|
| Create subscription | CreateSubscription order action |
| Add rate plan (amendment) | AddProduct order action |
| Remove rate plan (amendment) | RemoveProduct order action |
| Update rate plan (amendment) | UpdateProduct order action |
| Renew subscription | RenewSubscription order action |
| Cancel subscription | CancelSubscription order action |
| Suspend subscription | Suspend order action |
| Resume subscription | Resume order action |
| Terms & conditions change | TermsAndConditions order action |
| Owner transfer | OwnerTransfer order action |

### Subscribe Action API

| Legacy operation | Order API equivalent |
|---|---|
| Subscribe (new account) | `newAccount` + CreateSubscription order action |
| Subscribe (existing account) | `existingAccountNumber` + CreateSubscription order action |

## Key considerations

- Order API uses `orderDate` as the primary date anchor
- Multiple order actions can be combined in a single order (atomic)
- Future-dated actions are natively supported (schedule changes ahead of time)
- Charge overrides require `productRatePlanChargeId` — validate these exist
- Subscription terms configuration differs: use `terms` object in Order API
- Processing options (`runBilling`, `collectPayment`) are explicit per order

## Key Migration Principles

### 1. Processing Options Move to Order Level

Subscription API fields like `invoice`, `collect`, `invoiceCollect` move to order-level `processingOptions`:

**Subscription API:**
```json
{
  "invoiceCollect": true
}
```

**Order API:**
```json
{
  "processingOptions": {
    "runBilling": true,
    "collect": true
  }
}
```

### 2. Subscription Number Moves to Request Body

**Subscription API:**
```
PUT /v1/subscriptions/A-S00000123/cancel
```

**Order API:**
```json
POST /v1/orders
{
  "subscriptions": [{
    "subscriptionNumber": "A-S00000123",
    "orderActions": [...]
  }]
}
```

### 3. Contract Effective Date → Trigger Dates

**Subscription API:**
```json
{
  "contractEffectiveDate": "2026-12-31"
}
```

**Order API:**
```json
{
  "orderActions": [{
    "triggerDates": [{
      "name": "ContractEffective",
      "triggerDate": "2026-12-31"
    }]
  }]
}
```

### 4. Action Type Must Be Explicit

**Subscription API:** Action is implicit from endpoint (suspend, renew, cancel, etc.)

**Order API:** Action type must be specified explicitly:
```json
{
  "orderActions": [{
    "type": "Suspend"  // or "RenewSubscription", "Resume", "CancelSubscription", etc.
  }]
}
```

## Common Gotchas

### ❌ Incorrect: Specifying Renewal Terms in Order API

Renewal terms must be pre-configured on the subscription. Order API uses existing settings.

```json
// This does NOT work
{
  "renewSubscription": {
    "termType": "TERMED",
    "renewalTerm": 12
  }
}
```

### ✅ Correct: Order API Uses Subscription's Renewal Settings

```json
// Renew using subscription's existing renewal term configuration
{
  "type": "RenewSubscription",
  "triggerDates": [{
    "name": "ContractEffective",
    "triggerDate": "2026-05-01"
  }]
}
```

### ❌ Incorrect: extendsTerm in Suspend Action

```json
// This is wrong - extendsTerm belongs in Resume action
{
  "type": "Suspend",
  "suspend": {
    "extendsTerm": true
  }
}
```

### ✅ Correct: extendsTerm in Resume Action

```json
// When suspending with resume date, extendsTerm goes in Resume action
{
  "type": "Resume",
  "resume": {
    "resumeSpecificDate": "2026-04-21",
    "extendsTerm": true
  }
}
```

### ❌ Incorrect: Single Action for Suspend with Resume Date

```json
// This is incomplete - needs separate Resume action
{
  "type": "Suspend",
  "suspend": {
    "resumeSpecificDate": "2026-04-21"
  }
}
```

### ✅ Correct: Two Actions for Suspend with Resume

```json
// Requires two separate actions: Suspend + Resume
{
  "orderActions": [
    {
      "type": "Suspend",
      "triggerDates": [{
        "name": "ContractEffective",
        "triggerDate": "2026-04-01"
      }],
      "suspend": {
        "suspendPolicy": "SpecificDate",
        "suspendDate": "2026-04-01"
      }
    },
    {
      "type": "Resume",
      "resume": {
        "resumePolicy": "SpecificDate",
        "resumeSpecificDate": "2026-04-21",
        "extendsTerm": true
      }
    }
  ]
}
```

## Common edge cases

### Subscription/Amendment API
- **Mid-term changes**: Amendments mid-billing-period need careful effective date handling
- **Future-dated amendments**: Must convert to future-dated order actions
- **Custom fields**: Ensure custom fields are mapped correctly in order payloads
- **Charge-level overrides**: Price, quantity, and billing period overrides need explicit charge IDs
- **Multi-product subscriptions**: All rate plans must be handled in the migration
- **Termed vs evergreen**: Term type and auto-renew settings must be preserved
- **Suspend with resume date**: Requires TWO separate actions in Order API (Suspend + Resume)
- **extendsTerm field placement**: Must be in Resume action, not Suspend action

### Subscribe Action API
- **New vs existing account detection**: Must detect if `Account.accountKey` is present to determine account creation strategy
- **Payment method creation**: Order API can only create payment methods for new accounts (via `newAccount.paymentMethod`). For existing accounts, use Payment Methods API separately
- **Credit card field names**: Field names changed (`creditCardNumber` → `cardNumber`, `creditCardType` → `cardType`, `creditCardHolderName` → `cardHolderName`)
- **Term configuration structure**: Simple fields (`initialTerm`, `renewalTerm`) must be converted to structured `terms` object with `initialTerm`, `renewalTerms`, and `renewalSetting`
- **EVERGREEN subscriptions**: Must set `autoRenew: false` and omit `renewalTerms`
- **Contact information**: Both `billToContact` and `soldToContact` can be specified; if `soldToContact` is missing, it defaults to `billToContact`
- **Subscribe options mapping**: `generateInvoice` → `processingOptions.runBilling`, `processPayments` → `processingOptions.collect`

## Validation checklist

- All subscriptions accessible via Order API
- Billing behavior unchanged (invoice amounts, dates, frequencies)
- Subscription terms preserved (start date, end date, renewal settings)
- Custom field values preserved
- Amendments/changes work correctly via Order API
- Renewals and cancellations work correctly
- Reporting and analytics unaffected
- Downstream integrations receive correct data
- Response structure changes handled in all integration points
- Error handling updated for Order API error formats
- New required fields (orderDate, existingAccountNumber) sourced correctly

## Source Code Verification

All Subscription/Amendment to Order API field mappings are verified against Zuora Billing meta files:

**Subscription API Meta Classes:**
- `com.zuora.rest.meta.subscription.POSTSubscriptionRenewalMeta`
- `com.zuora.rest.meta.subscription.PUTSubscriptionSuspendMeta`
- `com.zuora.rest.meta.subscription.PUTSubscriptionResumeMeta`
- `com.zuora.rest.meta.subscription.POSTSubscriptionCancellationMeta`

**Order API Meta Classes:**
- `com.zuora.rest.meta.order.PostOrderActionRenewSubscriptionMeta`
- `com.zuora.rest.meta.order.PostOrderActionSuspendMeta`
- `com.zuora.rest.meta.order.PostOrderActionResumeMeta`
- `com.zuora.rest.meta.order.PostOrderActionCancelMeta`

## Detailed Reference Mappings

For field-level migration details, see:

### Subscription/Amendment API Mappings
- `amendment-rest-v1-cancel-api-mapping.md` - Cancel operation mapping
- `amendment-rest-v1-suspend-api-mapping.md` - Suspend operation mapping
- `amendment-rest-v1-resume-api-mapping.md` - Resume operation mapping
- `amendment-rest-v1-renew-api-mapping.md` - Renew operation mapping
- `amendment-rest-v1-create-api-mapping.md` - Create operation mapping
- `amendment-rest-v1-update-api-mapping.md` - Update operation mapping

### Subscribe Action API Mappings
- `action-subscribe-api-mapping.md` - Subscribe action mapping (account creation + subscription)
