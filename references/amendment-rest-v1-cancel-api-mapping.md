# Subscription Cancel API to Order API Migration Guide

Customer-facing guide for converting subscription cancellation from S/A API to Order API.

## Overview

This guide helps you migrate from the legacy Subscription Cancel API to the modern Order API.

### What You're Migrating

**FROM:** `PUT /v1/subscriptions/{subscription-key}/cancel`  
**TO:** `POST /v1/orders` with `CancelSubscription` action

## Quick Comparison

| Aspect | Subscription API | Order API |
|--------|------------------|-----------|
| Endpoint | `PUT /v1/subscriptions/{sub-key}/cancel` | `POST /v1/orders` |
| Action Type | Implicit (cancel) | Explicit (`CancelSubscription`) |
| Multiple Subscriptions | No | Yes (one order can cancel multiple subs) |
| Complexity | Simple | More flexible |

## Field Mapping

### Basic Cancel Request

**Subscription API:**
```json
PUT /v1/subscriptions/A-S00000123/cancel
{
  "cancellationPolicy": "SpecificDate",
  "cancellationEffectiveDate": "2026-09-01",
  "runBilling": true,
  "applyCreditBalance": true
}
```

**Order API:**
```json
POST /v1/orders
{
  "orderDate": "2026-09-01",
  "existingAccountNumber": "A00000001",
  "subscriptions": [
    {
      "subscriptionNumber": "A-S00000123",
      "orderActions": [
        {
          "type": "CancelSubscription",
          "triggerDates": [
            {
              "name": "ContractEffective",
              "triggerDate": "2026-09-01"
            }
          ],
          "cancelSubscription": {
            "cancellationPolicy": "SpecificDate",
            "cancellationEffectiveDate": "2026-09-01"
          }
        }
      ]
    }
  ],
  "processingOptions": {
    "runBilling": true,
    "applyCreditBalance": true
  }
}
```

### Complete Field Mapping Table

| Subscription Cancel Field | Order API Equivalent | Notes |
|---------------------------|----------------------|-------|
| `cancellationPolicy` | `subscriptions[].orderActions[].cancelSubscription.cancellationPolicy` | Same values: `EndOfCurrentTerm`, `EndOfLastInvoicePeriod`, `SpecificDate` |
| `cancellationEffectiveDate` | `subscriptions[].orderActions[].cancelSubscription.cancellationEffectiveDate` | Required when policy is `SpecificDate` |
| `runBilling` | `processingOptions.runBilling` | Generate invoice |
| `collect` | `processingOptions.collectPayment` | Collect payment |
| `applyCreditBalance` | `processingOptions.applyCreditBalance` | Apply credits |
| `targetDate` | `processingOptions.billingOptions.targetDate` | Invoice target date |
| `documentDate` | `processingOptions.billingOptions.documentDate` | Invoice document date |

### New Required Fields

Order API requires these additional fields:

- `orderDate` - The date of the order (typically today or cancellation date)
- `existingAccountNumber` - The account number (was implicit in subscription API)
- `subscriptionNumber` - Inside subscriptions array (was in URL path)

## Code Examples

### Python Example

**Before (Subscription API):**
```python
import requests

subscription_key = "A-S00000123"
url = f"https://rest.zuora.com/v1/subscriptions/{subscription_key}/cancel"

payload = {
    "cancellationPolicy": "SpecificDate",
    "cancellationEffectiveDate": "2026-09-01"
}

response = requests.put(url, json=payload, headers=headers)
```

**After (Order API):**
```python
import requests

url = "https://rest.zuora.com/v1/orders"

payload = {
    "orderDate": "2026-09-01",
    "existingAccountNumber": "A00000001",
    "subscriptions": [{
        "subscriptionNumber": "A-S00000123",
        "orderActions": [{
            "type": "CancelSubscription",
            "triggerDates": [{
                "name": "ContractEffective",
                "triggerDate": "2026-09-01"
            }],
            "cancelSubscription": {
                "cancellationPolicy": "SpecificDate",
                "cancellationEffectiveDate": "2026-09-01"
            }
        }]
    }]
}

response = requests.post(url, json=payload, headers=headers)
```

### Java Example

**Before (Subscription API):**
```java
String subscriptionKey = "A-S00000123";
String url = "https://rest.zuora.com/v1/subscriptions/" + subscriptionKey + "/cancel";

JSONObject payload = new JSONObject();
payload.put("cancellationPolicy", "SpecificDate");
payload.put("cancellationEffectiveDate", "2026-09-01");

// PUT request
HttpPut request = new HttpPut(url);
request.setEntity(new StringEntity(payload.toString()));
```

**After (Order API):**
```java
String url = "https://rest.zuora.com/v1/orders";

JSONObject payload = new JSONObject();
payload.put("orderDate", "2026-09-01");
payload.put("existingAccountNumber", "A00000001");

JSONArray subscriptions = new JSONArray();
JSONObject subscription = new JSONObject();
subscription.put("subscriptionNumber", "A-S00000123");

JSONArray orderActions = new JSONArray();
JSONObject action = new JSONObject();
action.put("type", "CancelSubscription");

JSONArray triggerDates = new JSONArray();
JSONObject triggerDate = new JSONObject();
triggerDate.put("name", "ContractEffective");
triggerDate.put("triggerDate", "2026-09-01");
triggerDates.put(triggerDate);
action.put("triggerDates", triggerDates);

JSONObject cancelSub = new JSONObject();
cancelSub.put("cancellationPolicy", "SpecificDate");
cancelSub.put("cancellationEffectiveDate", "2026-09-01");
action.put("cancelSubscription", cancelSub);

orderActions.put(action);
subscription.put("orderActions", orderActions);
subscriptions.put(subscription);
payload.put("subscriptions", subscriptions);

// POST request
HttpPost request = new HttpPost(url);
request.setEntity(new StringEntity(payload.toString()));
```

### JavaScript Example

**Before (Subscription API):**
```javascript
const subscriptionKey = 'A-S00000123';
const url = `https://rest.zuora.com/v1/subscriptions/${subscriptionKey}/cancel`;

const payload = {
  cancellationPolicy: 'SpecificDate',
  cancellationEffectiveDate: '2026-09-01'
};

const response = await fetch(url, {
  method: 'PUT',
  headers: headers,
  body: JSON.stringify(payload)
});
```

**After (Order API):**
```javascript
const url = 'https://rest.zuora.com/v1/orders';

const payload = {
  orderDate: '2026-09-01',
  existingAccountNumber: 'A00000001',
  subscriptions: [{
    subscriptionNumber: 'A-S00000123',
    orderActions: [{
      type: 'CancelSubscription',
      triggerDates: [{
        name: 'ContractEffective',
        triggerDate: '2026-09-01'
      }],
      cancelSubscription: {
        cancellationPolicy: 'SpecificDate',
        cancellationEffectiveDate: '2026-09-01'
      }
    }]
  }]
};

const response = await fetch(url, {
  method: 'POST',
  headers: headers,
  body: JSON.stringify(payload)
});
```

## Cancellation Policies

### EndOfCurrentTerm

Cancels subscription at the end of current term.

**Subscription API:**
```json
{
  "cancellationPolicy": "EndOfCurrentTerm"
}
```

**Order API:**
```json
{
  "cancelSubscription": {
    "cancellationPolicy": "EndOfCurrentTerm"
  }
}
```

### EndOfLastInvoicePeriod

Cancels at end of last invoice period.

**Subscription API:**
```json
{
  "cancellationPolicy": "EndOfLastInvoicePeriod"
}
```

**Order API:**
```json
{
  "cancelSubscription": {
    "cancellationPolicy": "EndOfLastInvoicePeriod"
  }
}
```

### SpecificDate

Cancels on a specific date (requires `cancellationEffectiveDate`).

**Subscription API:**
```json
{
  "cancellationPolicy": "SpecificDate",
  "cancellationEffectiveDate": "2026-09-01"
}
```

**Order API:**
```json
{
  "cancelSubscription": {
    "cancellationPolicy": "SpecificDate",
    "cancellationEffectiveDate": "2026-09-01"
  }
}
```

## Response Handling

### Subscription API Response

```json
{
  "success": true,
  "subscriptionId": "2c92a0fd...",
  "totalDeltaMrr": -100.00,
  "invoiceId": "2c92a0fe...",
  "creditMemoId": "2c92a0ff..."
}
```

### Order API Response

```json
{
  "success": true,
  "orderNumber": "O-00001234",
  "accountNumber": "A00000001",
  "status": "Pending",
  "subscriptions": [
    {
      "subscriptionNumber": "A-S00000123",
      "status": "Cancelled"
    }
  ],
  "invoiceNumbers": ["INV-00001234"],
  "creditMemoNumbers": ["CM-00001234"]
}
```

**Key Differences:**
- Order API returns `orderNumber` instead of `subscriptionId`
- Order API includes full subscription details in array
- Order API returns arrays for invoices/credit memos (supports multiple)

## Migration Checklist

- [ ] Identify all subscription cancel API calls in your code
- [ ] Update endpoint from `PUT /v1/subscriptions/{key}/cancel` to `POST /v1/orders`
- [ ] Add required `orderDate` field
- [ ] Add required `existingAccountNumber` field
- [ ] Wrap cancel parameters in `cancelSubscription` object
- [ ] Nest cancel in `orderActions` array
- [ ] Nest actions in `subscriptions` array
- [ ] Move billing options to `processingOptions`
- [ ] Update response handling for new structure
- [ ] Test in sandbox environment
- [ ] Update error handling for Order API errors

## Common Migration Patterns

### Pattern 1: Simple Cancel with Billing

**Before:**
```json
PUT /v1/subscriptions/A-S00000123/cancel
{
  "cancellationPolicy": "EndOfCurrentTerm",
  "runBilling": true
}
```

**After:**
```json
POST /v1/orders
{
  "orderDate": "2026-04-07",
  "existingAccountNumber": "A00000001",
  "subscriptions": [{
    "subscriptionNumber": "A-S00000123",
    "orderActions": [{
      "type": "CancelSubscription",
      "cancelSubscription": {
        "cancellationPolicy": "EndOfCurrentTerm"
      }
    }]
  }],
  "processingOptions": {
    "runBilling": true
  }
}
```

### Pattern 2: Cancel Multiple Subscriptions

**Before (required multiple API calls):**
```json
PUT /v1/subscriptions/A-S00000123/cancel
PUT /v1/subscriptions/A-S00000124/cancel
```

**After (single API call):**
```json
POST /v1/orders
{
  "orderDate": "2026-04-07",
  "existingAccountNumber": "A00000001",
  "subscriptions": [
    {
      "subscriptionNumber": "A-S00000123",
      "orderActions": [{"type": "CancelSubscription", ...}]
    },
    {
      "subscriptionNumber": "A-S00000124",
      "orderActions": [{"type": "CancelSubscription", ...}]
    }
  ]
}
```

## Benefits of Order API

1. **Bulk Operations**: Cancel multiple subscriptions in one call
2. **Better Tracking**: Order number for audit trail
3. **Flexibility**: Combine cancel with other actions
4. **Future-Proof**: Order API is the strategic direction

## Resources

- [Order API Documentation](https://www.zuora.com/developer/api-references/api/tag/Orders)
- [Subscription API Documentation](https://www.zuora.com/developer/api-references/api/tag/Subscriptions)
- [Migration Best Practices](https://knowledgecenter.zuora.com/)
