# Subscription Renew API to Order API Migration Guide

Customer-facing guide for converting subscription renewal operations from S/A API to Order API.

## Overview

This guide helps you migrate from the legacy Subscription Renew API to the modern Order API.

**IMPORTANT:** The Subscription Renew API and Order API's `RenewSubscription` action both renew a subscription using its **existing renewal term settings**. Neither API allows you to specify custom renewal terms in the renewal request - the subscription must already be configured with the desired renewal term and type.

### What You're Migrating

**FROM:** `PUT /v1/subscriptions/{subscription-key}/renew`

**TO:** `POST /v1/orders` with `RenewSubscription` action

## Quick Comparison

| Aspect | Subscription API | Order API |
|--------|------------------|-----------|
| Endpoint | `PUT /v1/subscriptions/{sub-key}/renew` | `POST /v1/orders` |
| Action Type | Implicit (renew) | Explicit (`RenewSubscription`) |
| Multiple Subscriptions | No (one per call) | Yes (one order can affect multiple subs) |
| Renewal Term Source | Uses subscription's existing renewal settings | Uses subscription's existing renewal settings |
| Billing/Contact Updates | Not supported | Supported (optional fields) |
| Processing Options | In request body | In `processingOptions` |

## Renew API Field Mapping

### Basic Renewal Request

**Subscription API:**
```json
PUT /v1/subscriptions/A-S00000123/renew
{
  "contractEffectiveDate": "2026-12-31",
  "invoiceCollect": true
}
```

**Order API:**
```json
POST /v1/orders
{
  "orderDate": "2026-12-31",
  "existingAccountNumber": "A00000001",
  "subscriptions": [
    {
      "subscriptionNumber": "A-S00000123",
      "orderActions": [
        {
          "type": "RenewSubscription",
          "triggerDates": [
            {
              "name": "ContractEffective",
              "triggerDate": "2026-12-31"
            }
          ]
        }
      ]
    }
  ],
  "processingOptions": {
    "runBilling": true,
    "collect": true
  }
}
```

### Renewal with Billing Contact Update

The Order API allows you to optionally update billing and contact information during renewal:

**Order API:**
```json
POST /v1/orders
{
  "orderDate": "2026-12-31",
  "existingAccountNumber": "A00000001",
  "subscriptions": [
    {
      "subscriptionNumber": "A-S00000123",
      "orderActions": [
        {
          "type": "RenewSubscription",
          "triggerDates": [
            {
              "name": "ContractEffective",
              "triggerDate": "2026-12-31"
            }
          ]
        }
      ]
    }
  ],
  "processingOptions": {
    "runBilling": true,
    "collect": true
  }
}
```

### Renew Field Mapping Table

| Subscription Renew Field | Order API Equivalent | Notes |
|--------------------------|----------------------|-------|
| `contractEffectiveDate` | `triggerDates[].triggerDate` | Renewal effective date |
| `orderDate` | `orderDate` | Order creation date (top level) |
| **invoiceCollectRequest** fields: | | |
| `invoiceCollect` | `processingOptions.runBilling` + `processingOptions.collect` | Split into two separate flags |
| `invoice` / `runBilling` | `processingOptions.runBilling` | Generate invoice |
| `collect` | `processingOptions.collect` | Collect payment |
| `applyCreditBalance` | `processingOptions.applyCreditBalance` | Apply credit balance |
| `applyCredit` | `processingOptions.applyCredit` | Apply credit memos |
| `applicationOrder` | `processingOptions.applicationOrder` | AR application order |
| `invoiceRequest.targetDate` | `processingOptions.billingOptions.targetDate` | Invoice target date |
| `invoiceRequest.documentDate` | `processingOptions.billingOptions.documentDate` | Document date |
| `gatewayId` | `processingOptions.gatewayId` | Payment gateway ID |
| `paymentMethodId` | `processingOptions.paymentMethodId` | Payment method ID |
| `creditMemoReasonCode` | `processingOptions.billingOptions.creditMemoReasonCode` | Credit memo reason |
| N/A (implicit in URL) | `subscriptionNumber` | Now in request body |
| N/A (from subscription) | `existingAccountNumber` | Required field |

### Optional RenewSubscription Action Fields

The Order API's `RenewSubscription` action supports these optional fields to update billing and contact information:

| Field | Type | Description |
|-------|------|-------------|
| `billToContactId` | String | Update bill-to contact (32-36 chars) |
| `paymentTerm` | String | Update payment term (max 100 chars) |
| `clearingExistingPaymentTerm` | Boolean | Clear existing payment term |
| `clearingExistingBillToContact` | Boolean | Clear existing bill-to contact |
| `clearingExistingInvoiceTemplate` | Boolean | Clear existing invoice template |
| `clearingExistingSequenceSet` | Boolean | Clear existing sequence set |
| `invoiceTemplateId` | String | Update invoice template (max 32 chars) |
| `sequenceSetId` | String | Update sequence set (max 32 chars) |
| `soldToContactId` | String | Update sold-to contact (32-36 chars) |
| `clearingExistingSoldToContact` | Boolean | Clear existing sold-to contact |
| `shipToContactId` | String | Update ship-to contact (32-36 chars) |
| `clearingExistingShipToContact` | Boolean | Clear existing ship-to contact |
| `invoiceGroupNumber` | String | Update invoice group number (1-255 chars) |
| `clearingExistingInvoiceGroupNumber` | Boolean | Clear existing invoice group number |
| `communicationProfileId` | String | Update communication profile |
| `clearingExistingCommunicationProfile` | Boolean | Clear existing communication profile |

### New Required Fields

Order API requires these additional fields:

- `orderDate` - The date of the order
- `existingAccountNumber` - The account number
- `subscriptionNumber` - Inside subscriptions array (was in URL path)

## Code Examples

### Python - Basic Renewal

**Before (Subscription API):**
```python
import requests

subscription_key = "A-S00000123"
url = f"https://rest.zuora.com/v1/subscriptions/{subscription_key}/renew"

payload = {
    "contractEffectiveDate": "2026-12-31",
    "invoiceCollect": True
}

response = requests.put(url, json=payload, headers=headers)
```

**After (Order API):**
```python
import requests

url = "https://rest.zuora.com/v1/orders"

payload = {
    "orderDate": "2026-12-31",
    "existingAccountNumber": "A00000001",  # NEW: Required
    "subscriptions": [{
        "subscriptionNumber": "A-S00000123",
        "orderActions": [{
            "type": "RenewSubscription",
            "triggerDates": [{
                "name": "ContractEffective",
                "triggerDate": "2026-12-31"
            }]
        }]
    }],
    "processingOptions": {
        "runBilling": True,  # Replaces "invoiceCollect"
        "collect": True
    }
}

response = requests.post(url, json=payload, headers=headers)
```

### Python - Renewal with Billing Contact Update

**After (Order API):**
```python
import requests

url = "https://rest.zuora.com/v1/orders"

payload = {
    "orderDate": "2026-12-31",
    "existingAccountNumber": "A00000001",
    "subscriptions": [{
        "subscriptionNumber": "A-S00000123",
        "orderActions": [{
            "type": "RenewSubscription",
            "triggerDates": [{
                "name": "ContractEffective",
                "triggerDate": "2026-12-31"
            }],
            "renewSubscription": {
                "billToContactId": "2c92c0f84d1e4f8a014d1e5a8c5e0123",
                "paymentTerm": "Net 30",
                "invoiceTemplateId": "2c92c0f84d1e4f8a014d1e5a8c5e0456"
            }
        }]
    }],
    "processingOptions": {
        "runBilling": True,
        "collect": True
    }
}

response = requests.post(url, json=payload, headers=headers)
```

### Java - Basic Renewal

**Before (Subscription API):**
```java
String subscriptionKey = "A-S00000123";
String url = "https://rest.zuora.com/v1/subscriptions/" + subscriptionKey + "/renew";

JSONObject payload = new JSONObject();
payload.put("contractEffectiveDate", "2026-12-31");

JSONObject invoiceCollectRequest = new JSONObject();
invoiceCollectRequest.put("invoiceCollect", true);
payload.put("invoiceCollectRequest", invoiceCollectRequest);

HttpPut request = new HttpPut(url);
request.setEntity(new StringEntity(payload.toString()));
HttpResponse response = httpClient.execute(request);
```

**After (Order API):**
```java
String url = "https://rest.zuora.com/v1/orders";

JSONObject payload = new JSONObject();
payload.put("orderDate", "2026-12-31");
payload.put("existingAccountNumber", "A00000001");

JSONArray subscriptions = new JSONArray();
JSONObject subscription = new JSONObject();
subscription.put("subscriptionNumber", "A-S00000123");

JSONArray orderActions = new JSONArray();
JSONObject action = new JSONObject();
action.put("type", "RenewSubscription");

JSONArray triggerDates = new JSONArray();
JSONObject triggerDate = new JSONObject();
triggerDate.put("name", "ContractEffective");
triggerDate.put("triggerDate", "2026-12-31");
triggerDates.put(triggerDate);
action.put("triggerDates", triggerDates);

orderActions.put(action);
subscription.put("orderActions", orderActions);
subscriptions.put(subscription);
payload.put("subscriptions", subscriptions);

JSONObject processingOptions = new JSONObject();
processingOptions.put("runBilling", true);
processingOptions.put("collect", true);
payload.put("processingOptions", processingOptions);

HttpPost request = new HttpPost(url);
request.setEntity(new StringEntity(payload.toString()));
HttpResponse response = httpClient.execute(request);
```

### JavaScript - Basic Renewal

**Before (Subscription API):**
```javascript
const subscriptionKey = 'A-S00000123';
const url = `https://rest.zuora.com/v1/subscriptions/${subscriptionKey}/renew`;

const payload = {
  contractEffectiveDate: '2026-12-31',
  invoiceCollectRequest: {
    invoiceCollect: true
  }
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
  orderDate: '2026-12-31',
  existingAccountNumber: 'A00000001',
  subscriptions: [{
    subscriptionNumber: 'A-S00000123',
    orderActions: [{
      type: 'RenewSubscription',
      triggerDates: [{
        name: 'ContractEffective',
        triggerDate: '2026-12-31'
      }]
    }]
  }],
  processingOptions: {
    runBilling: true,  // Replaces "invoice" or "invoiceCollect"
    collect: true
  }
};

const response = await fetch(url, {
  method: 'POST',
  headers: headers,
  body: JSON.stringify(payload)
});
```

### JavaScript - Renewal with Invoice and Collection Options

**Before (Subscription API):**
```javascript
const subscriptionKey = 'A-S00000123';
const url = `https://rest.zuora.com/v1/subscriptions/${subscriptionKey}/renew`;

const payload = {
  contractEffectiveDate: '2027-01-01',
  invoiceCollectRequest: {
    runBilling: true,
    collect: true,
    applyCreditBalance: true,
    invoiceRequest: {
      targetDate: '2027-01-01',
      documentDate: '2027-01-01'
    },
    paymentMethodId: '2c92c0f84d1e4f8a014d1e5a8c5e0789'
  }
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
  orderDate: '2027-01-01',
  existingAccountNumber: 'A00000001',
  subscriptions: [{
    subscriptionNumber: 'A-S00000123',
    orderActions: [{
      type: 'RenewSubscription',
      triggerDates: [{
        name: 'ContractEffective',
        triggerDate: '2027-01-01'
      }]
    }]
  }],
  processingOptions: {
    runBilling: true,
    collect: true,
    applyCreditBalance: true,
    billingOptions: {
      targetDate: '2027-01-01',
      documentDate: '2027-01-01'
    },
    paymentMethodId: '2c92c0f84d1e4f8a014d1e5a8c5e0789'
  }
};

const response = await fetch(url, {
  method: 'POST',
  headers: headers,
  body: JSON.stringify(payload)
});
```

## Processing Options

Several Subscription API fields move to `processingOptions` at the order level in Order API:

| Subscription API | Order API | Description |
|------------------|-----------|-------------|
| `invoiceCollect` | `runBilling: true` + `collect: true` | Combined billing and payment |
| `invoice` / `runBilling` | `processingOptions.runBilling` | Generate invoice for renewal |
| `collect` | `processingOptions.collect` | Collect payment after renewal |
| `applyCreditBalance` | `processingOptions.applyCreditBalance` | Apply credit balance |
| `applyCredit` | `processingOptions.applyCredit` | Apply credit memos |
| `applicationOrder` | `processingOptions.applicationOrder` | AR application order |
| `invoiceRequest.*` | `processingOptions.billingOptions.*` | Invoice-specific options |
| `gatewayId` | `processingOptions.gatewayId` | Payment gateway |
| `paymentMethodId` | `processingOptions.paymentMethodId` | Payment method |
| `creditMemoReasonCode` | `processingOptions.billingOptions.creditMemoReasonCode` | Credit memo reason |

**Example:**
```json
{
  "processingOptions": {
    "runBilling": true,
    "collect": true,
    "applyCreditBalance": true,
    "billingOptions": {
      "targetDate": "2027-01-01",
      "documentDate": "2027-01-01",
      "creditMemoReasonCode": "REFUND"
    },
    "paymentMethodId": "2c92c0f84d1e4f8a014d1e5a8c5e0789"
  }
}
```

## Key Differences Summary

| Scenario | Subscription API | Order API |
|----------|------------------|-----------|
| Basic renewal | `contractEffectiveDate` + `invoiceCollectRequest` | `triggerDates` + `processingOptions` |
| Renewal term source | Uses subscription's renewal settings | Uses subscription's renewal settings |
| Invoice generation | `invoiceCollect: true` or `invoice: true` | `processingOptions.runBilling: true` |
| Payment collection | `invoiceCollect: true` or `collect: true` | `processingOptions.collect: true` |
| Multiple renewals | Multiple API calls required | Single order with multiple subscriptions |
| Update billing info | Not supported | Optional `renewSubscription` fields |

## Response Handling

### Subscription API Response

```json
{
  "success": true,
  "subscriptionId": "2c92a0fd...",
  "termStartDate": "2027-01-01",
  "termEndDate": "2027-12-31",
  "totalDeltaMrr": 0.00,
  "totalDeltaTcv": 12000.00,
  "invoiceId": "2c92a0fe...",
  "paidAmount": 12000.00
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
      "status": "Active",
      "termStartDate": "2027-01-01",
      "termEndDate": "2027-12-31",
      "currentTermPeriodType": "Month",
      "currentTerm": 12
    }
  ],
  "invoiceNumbers": ["INV-00001234"]
}
```

**Key Differences:**
- Order API returns `orderNumber` instead of just `subscriptionId`
- Order API includes full subscription details with status
- Order API returns `invoiceNumbers` array instead of single `invoiceId`
- Order API response structure is consistent across all operations

## Migration Checklist

- [ ] Identify all subscription renew API calls in your code
- [ ] Update endpoint from `PUT /v1/subscriptions/{key}/renew` to `POST /v1/orders`
- [ ] Add required `orderDate` field
- [ ] Add required `existingAccountNumber` field
- [ ] Change action type to `"RenewSubscription"`
- [ ] Move `invoiceCollectRequest` fields to `processingOptions`
- [ ] Update `invoice`/`invoiceCollect` to `runBilling` in processing options
- [ ] Move `invoiceRequest.*` fields to `processingOptions.billingOptions.*`
- [ ] Nest actions in `orderActions` array
- [ ] Add `triggerDates` array with contract effective date
- [ ] (Optional) Add `renewSubscription` fields if updating billing/contact info
- [ ] Update response handling for new structure
- [ ] Test in sandbox environment

## Common Migration Patterns

### Pattern 1: Simple Renewal

**Before:**
```json
PUT /v1/subscriptions/A-S00000123/renew
{
  "contractEffectiveDate": "2026-12-31"
}
```

**After:**
```json
POST /v1/orders
{
  "orderDate": "2026-12-31",
  "existingAccountNumber": "A00000001",
  "subscriptions": [{
    "subscriptionNumber": "A-S00000123",
    "orderActions": [{
      "type": "RenewSubscription",
      "triggerDates": [{
        "name": "ContractEffective",
        "triggerDate": "2026-12-31"
      }]
    }]
  }]
}
```

### Pattern 2: Renewal with Invoice and Payment

**Before:**
```json
PUT /v1/subscriptions/A-S00000123/renew
{
  "contractEffectiveDate": "2027-01-01",
  "invoiceCollectRequest": {
    "invoiceCollect": true
  }
}
```

**After:**
```json
POST /v1/orders
{
  "orderDate": "2027-01-01",
  "existingAccountNumber": "A00000001",
  "subscriptions": [{
    "subscriptionNumber": "A-S00000123",
    "orderActions": [{
      "type": "RenewSubscription",
      "triggerDates": [{
        "name": "ContractEffective",
        "triggerDate": "2027-01-01"
      }]
    }]
  }],
  "processingOptions": {
    "runBilling": true,
    "collect": true
  }
}
```

### Pattern 3: Renewal with Billing Contact Update

**After (Order API only):**
```json
POST /v1/orders
{
  "orderDate": "2026-12-31",
  "existingAccountNumber": "A00000001",
  "subscriptions": [{
    "subscriptionNumber": "A-S00000123",
    "orderActions": [{
      "type": "RenewSubscription",
      "triggerDates": [{
        "name": "ContractEffective",
        "triggerDate": "2026-12-31"
      }],
      "renewSubscription": {
        "billToContactId": "2c92c0f84d1e4f8a014d1e5a8c5e0123",
        "paymentTerm": "Net 30"
      }
    }]
  }],
  "processingOptions": {
    "runBilling": true,
    "collect": true
  }
}
```

### Pattern 4: Renew Multiple Subscriptions

**Before (required multiple API calls):**
```json
PUT /v1/subscriptions/A-S00000123/renew
PUT /v1/subscriptions/A-S00000124/renew
```

**After (single API call):**
```json
POST /v1/orders
{
  "orderDate": "2026-12-31",
  "existingAccountNumber": "A00000001",
  "subscriptions": [
    {
      "subscriptionNumber": "A-S00000123",
      "orderActions": [{
        "type": "RenewSubscription",
        "triggerDates": [{
          "name": "ContractEffective",
          "triggerDate": "2026-12-31"
        }]
      }]
    },
    {
      "subscriptionNumber": "A-S00000124",
      "orderActions": [{
        "type": "RenewSubscription",
        "triggerDates": [{
          "name": "ContractEffective",
          "triggerDate": "2026-12-31"
        }]
      }]
    }
  ],
  "processingOptions": {
    "runBilling": true,
    "collect": true
  }
}
```

### Pattern 5: Renewal with Advanced Billing Options

**Before:**
```json
PUT /v1/subscriptions/A-S00000123/renew
{
  "contractEffectiveDate": "2027-01-01",
  "invoiceCollectRequest": {
    "runBilling": true,
    "collect": true,
    "applyCreditBalance": true,
    "invoiceRequest": {
      "targetDate": "2027-01-01",
      "documentDate": "2027-01-01"
    },
    "paymentMethodId": "2c92c0f84d1e4f8a014d1e5a8c5e0789",
    "gatewayId": "2c92c0f84d1e4f8a014d1e5a8c5e0456"
  }
}
```

**After:**
```json
POST /v1/orders
{
  "orderDate": "2027-01-01",
  "existingAccountNumber": "A00000001",
  "subscriptions": [{
    "subscriptionNumber": "A-S00000123",
    "orderActions": [{
      "type": "RenewSubscription",
      "triggerDates": [{
        "name": "ContractEffective",
        "triggerDate": "2027-01-01"
      }]
    }]
  }],
  "processingOptions": {
    "runBilling": true,
    "collect": true,
    "applyCreditBalance": true,
    "billingOptions": {
      "targetDate": "2027-01-01",
      "documentDate": "2027-01-01"
    },
    "paymentMethodId": "2c92c0f84d1e4f8a014d1e5a8c5e0789",
    "gatewayId": "2c92c0f84d1e4f8a014d1e5a8c5e0456"
  }
}
```

## Benefits of Order API

1. **Bulk Operations**: Renew multiple subscriptions in one call
2. **Combined Actions**: Combine renewal with other order actions
3. **Better Tracking**: Order number for complete audit trail
4. **Consistency**: Same endpoint for all subscription modifications
5. **Flexibility**: Update billing/contact info during renewal
6. **Future-Proof**: Order API is the strategic direction

## Important Notes

### Renewal Term Source

**CRITICAL:** Both the Subscription Renew API and Order API's `RenewSubscription` action renew a subscription using its **existing renewal term settings**. The subscription must already be configured with:
- Auto-renewal term length (e.g., 12 months)
- Auto-renewal term type (e.g., Month, Year)
- Auto-renewal status (enabled)

**You cannot specify custom renewal terms in the renewal request.** If you need to change the renewal term, you must update the subscription's renewal settings **before** calling the renewal API.

### Invoice and Collection

**Subscription API:**
- `invoiceCollect: true` - Both generate invoice AND collect payment
- `invoice: true` or `runBilling: true` - Generate invoice only
- `collect: true` - Collect payment only

**Order API:**
- `runBilling: true` - Generate invoice (renamed from `invoice`)
- `collect: true` - Collect payment (separate flag)
- For `invoiceCollect` behavior: set both `runBilling: true` and `collect: true`

### Billing Options

Invoice-specific options move from `invoiceRequest` to `processingOptions.billingOptions`:
- `targetDate` - Invoice target date
- `documentDate` - Invoice document date
- `creditMemoReasonCode` - Credit memo reason code

### Renewal Timing

- Renewals typically occur at the end of the current term
- You can trigger an early renewal by specifying a `contractEffectiveDate` before the term end date
- The renewal will use the subscription's configured auto-renewal term

## Error Handling

### Common Errors

**Error: Missing existingAccountNumber**
```json
{
  "success": false,
  "reasons": [{
    "code": 53100320,
    "message": "existingAccountNumber is required"
  }]
}
```
**Solution:** Add the account number to your order request.

**Error: Subscription not configured for auto-renewal**
```json
{
  "success": false,
  "reasons": [{
    "code": 53100080,
    "message": "Subscription is not eligible for renewal. Auto-renewal must be enabled."
  }]
}
```
**Solution:** Enable auto-renewal on the subscription and configure the renewal term settings before attempting renewal.

**Error: Subscription already renewed**
```json
{
  "success": false,
  "reasons": [{
    "code": 53100070,
    "message": "Subscription has already been renewed for this term"
  }]
}
```
**Solution:** Check if the subscription has already been renewed. Cannot renew twice for the same term.

**Error: Invalid bill-to contact**
```json
{
  "success": false,
  "reasons": [{
    "code": 53100040,
    "message": "Invalid billToContactId"
  }]
}
```
**Solution:** Verify the contact ID exists and belongs to the correct account.

## Resources

- [Order API Documentation](https://www.zuora.com/developer/api-references/api/tag/Orders)
- [Subscription API Documentation](https://www.zuora.com/developer/api-references/api/tag/Subscriptions)
- [Renewal Operation Guide](https://knowledgecenter.zuora.com/)
- [Subscription Renewal Settings](https://knowledgecenter.zuora.com/Zuora_Billing/Manage_subscription_transactions/Subscriptions/Renew_subscriptions)
