# Subscription Resume API to Order API Migration Guide

Customer-facing guide for converting subscription resume operations from S/A API to Order API.

## Overview

This guide helps you migrate from the legacy Subscription Resume API to the modern Order API.

The Subscription Resume API allows you to:
- Resume a previously suspended subscription
- Specify the resume date and term extension behavior

### What You're Migrating

**FROM:** `PUT /v1/subscriptions/{subscription-key}/resume`

**TO:** `POST /v1/orders` with `Resume` action

## Quick Comparison

| Aspect | Subscription API | Order API |
|--------|------------------|-----------|
| Endpoint | `PUT /v1/subscriptions/{sub-key}/resume` | `POST /v1/orders` |
| Action Type | Implicit (resume) | Explicit (`Resume`) |
| Multiple Subscriptions | No (one per call) | Yes (one order can affect multiple subs) |
| Complexity | Simple | More flexible |

## Resume API Field Mapping

### Basic Resume Request

**Subscription API:**
```json
PUT /v1/subscriptions/A-S00000123/resume
{
  "resumeDate": "2026-05-01",
  "contractEffectiveDate": "2026-05-01",
  "resumePolicy": "SpecificDate",
  "resumeSpecificDate": "2026-05-01",
  "extendsTerm": false
}
```

**Order API:**
```json
POST /v1/orders
{
  "orderDate": "2026-05-01",
  "existingAccountNumber": "A00000001",
  "subscriptions": [
    {
      "subscriptionNumber": "A-S00000123",
      "orderActions": [
        {
          "type": "Resume",
          "triggerDates": [
            {
              "name": "ContractEffective",
              "triggerDate": "2026-05-01"
            }
          ],
          "resume": {
            "resumePolicy": "SpecificDate",
            "resumeSpecificDate": "2026-05-01",
            "extendsTerm": false
          }
        }
      ]
    }
  ]
}
```

### Resume with SpecificDate Policy

**Subscription API:**
```json
PUT /v1/subscriptions/A-S00000123/resume
{
  "contractEffectiveDate": "2026-04-21",
  "resumePolicy": "SpecificDate",
  "resumeSpecificDate": "2026-04-21",
  "extendsTerm": true
}
```

**Order API:**
```json
POST /v1/orders
{
  "orderDate": "2026-04-21",
  "existingAccountNumber": "A00000001",
  "subscriptions": [
    {
      "subscriptionNumber": "A-S00000123",
      "orderActions": [
        {
          "type": "Resume",
          "triggerDates": [
            {
              "name": "ContractEffective",
              "triggerDate": "2026-04-21"
            }
          ],
          "resume": {
            "resumePolicy": "SpecificDate",
            "resumeSpecificDate": "2026-04-21",
            "extendsTerm": true
          }
        }
      ]
    }
  ]
}
```

### Resume Field Mapping Table

| Subscription Resume Field | Order API Equivalent | Notes |
|---------------------------|----------------------|-------|
| `contractEffectiveDate` | `triggerDates[].triggerDate` | Primary trigger date for the Resume action |
| `resumePolicy` | `subscriptions[].orderActions[].resume.resumePolicy` | Values: `SpecificDate`, `FixedPeriodsFromSuspendDate` |
| `resumeSpecificDate` | `subscriptions[].orderActions[].resume.resumeSpecificDate` AND `triggerDates[].triggerDate` (in Resume action) | Required when `resumePolicy` is `SpecificDate` |
| `resumePeriods` | `subscriptions[].orderActions[].resume.resumePeriods` | Number of periods from suspend date to resume |
| `resumePeriodsType` | `subscriptions[].orderActions[].resume.resumePeriodsType` | Values: `Day`, `Week`, `Month`, `Year` |
| `extendsTerm` | `subscriptions[].orderActions[].resume.extendsTerm` | Extends subscription term by the suspension duration |
| N/A (implicit in URL) | `subscriptionNumber` | Now in request body |
| N/A (from subscription) | `existingAccountNumber` | Required field |

### New Required Fields

Order API requires these additional fields:

- `orderDate` - The date of the order
- `existingAccountNumber` - The account number
- `subscriptionNumber` - Inside subscriptions array (was in URL path)

## Code Examples

### Python - Resume Subscription

**Before (Subscription API):**
```python
import requests

subscription_key = "A-S00000123"
url = f"https://rest.zuora.com/v1/subscriptions/{subscription_key}/resume"

payload = {
    "resumeDate": "2026-05-01",
    "contractEffectiveDate": "2026-05-01",
    "resumePolicy": "SpecificDate",
    "resumeSpecificDate": "2026-05-01",
    "extendsTerm": False
}

response = requests.put(url, json=payload, headers=headers)
```

**After (Order API):**
```python
import requests

url = "https://rest.zuora.com/v1/orders"

payload = {
    "orderDate": "2026-05-01",
    "existingAccountNumber": "A00000001",  # NEW: Required
    "subscriptions": [{
        "subscriptionNumber": "A-S00000123",
        "orderActions": [{
            "type": "Resume",
            "triggerDates": [{
                "name": "ContractEffective",
                "triggerDate": "2026-05-01"
            }],
            "resume": {
                "resumePolicy": "SpecificDate",
                "resumeSpecificDate": "2026-05-01",
                "extendsTerm": False
            }
        }]
    }]
}

response = requests.post(url, json=payload, headers=headers)
```

### Python - Resume with Term Extension

**Before (Subscription API):**
```python
import requests

subscription_key = "A-S00000123"
url = f"https://rest.zuora.com/v1/subscriptions/{subscription_key}/resume"

payload = {
    "contractEffectiveDate": "2026-04-21",
    "resumePolicy": "SpecificDate",
    "resumeSpecificDate": "2026-04-21",
    "extendsTerm": True  # Extend term by suspension duration
}

response = requests.put(url, json=payload, headers=headers)
```

**After (Order API):**
```python
import requests

url = "https://rest.zuora.com/v1/orders"

payload = {
    "orderDate": "2026-04-21",
    "existingAccountNumber": "A00000001",
    "subscriptions": [{
        "subscriptionNumber": "A-S00000123",
        "orderActions": [{
            "type": "Resume",
            "triggerDates": [{
                "name": "ContractEffective",
                "triggerDate": "2026-04-21"
            }],
            "resume": {
                "resumePolicy": "SpecificDate",
                "resumeSpecificDate": "2026-04-21",
                "extendsTerm": True
            }
        }]
    }]
}

response = requests.post(url, json=payload, headers=headers)
```

### Java - Resume Subscription

**Before (Subscription API):**
```java
String subscriptionKey = "A-S00000123";
String url = "https://rest.zuora.com/v1/subscriptions/" + subscriptionKey + "/resume";

JSONObject payload = new JSONObject();
payload.put("resumeDate", "2026-05-01");
payload.put("contractEffectiveDate", "2026-05-01");
payload.put("resumePolicy", "SpecificDate");
payload.put("resumeSpecificDate", "2026-05-01");
payload.put("extendsTerm", false);

HttpPut request = new HttpPut(url);
request.setEntity(new StringEntity(payload.toString()));
HttpResponse response = httpClient.execute(request);
```

**After (Order API):**
```java
String url = "https://rest.zuora.com/v1/orders";

JSONObject payload = new JSONObject();
payload.put("orderDate", "2026-05-01");
payload.put("existingAccountNumber", "A00000001");

JSONArray subscriptions = new JSONArray();
JSONObject subscription = new JSONObject();
subscription.put("subscriptionNumber", "A-S00000123");

JSONArray orderActions = new JSONArray();
JSONObject action = new JSONObject();
action.put("type", "Resume");

JSONArray triggerDates = new JSONArray();
JSONObject triggerDate = new JSONObject();
triggerDate.put("name", "ContractEffective");
triggerDate.put("triggerDate", "2026-05-01");
triggerDates.put(triggerDate);
action.put("triggerDates", triggerDates);

JSONObject resume = new JSONObject();
resume.put("resumePolicy", "SpecificDate");
resume.put("resumeSpecificDate", "2026-05-01");
resume.put("extendsTerm", false);
action.put("resume", resume);

orderActions.put(action);
subscription.put("orderActions", orderActions);
subscriptions.put(subscription);
payload.put("subscriptions", subscriptions);

HttpPost request = new HttpPost(url);
request.setEntity(new StringEntity(payload.toString()));
HttpResponse response = httpClient.execute(request);
```

### JavaScript - Resume Subscription

**Before (Subscription API):**
```javascript
const subscriptionKey = 'A-S00000123';
const url = `https://rest.zuora.com/v1/subscriptions/${subscriptionKey}/resume`;

const payload = {
  resumeDate: '2026-05-01',
  contractEffectiveDate: '2026-05-01',
  resumePolicy: 'SpecificDate',
  resumeSpecificDate: '2026-05-01',
  extendsTerm: false
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
  orderDate: '2026-05-01',
  existingAccountNumber: 'A00000001',
  subscriptions: [{
    subscriptionNumber: 'A-S00000123',
    orderActions: [{
      type: 'Resume',
      triggerDates: [{
        name: 'ContractEffective',
        triggerDate: '2026-05-01'
      }],
      resume: {
        resumePolicy: 'SpecificDate',
        resumeSpecificDate: '2026-05-01',
        extendsTerm: false
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

### JavaScript - Resume with Term Extension

**Before (Subscription API):**
```javascript
const subscriptionKey = 'A-S00000123';
const url = `https://rest.zuora.com/v1/subscriptions/${subscriptionKey}/resume`;

const payload = {
  contractEffectiveDate: '2026-04-21',
  resumePolicy: 'SpecificDate',
  resumeSpecificDate: '2026-04-21',
  extendsTerm: true
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
  orderDate: '2026-04-21',
  existingAccountNumber: 'A00000001',
  subscriptions: [{
    subscriptionNumber: 'A-S00000123',
    orderActions: [{
      type: 'Resume',
      triggerDates: [{
        name: 'ContractEffective',
        triggerDate: '2026-04-21'
      }],
      resume: {
        resumePolicy: 'SpecificDate',
        resumeSpecificDate: '2026-04-21',
        extendsTerm: true
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

## Resume Policies

The `resumePolicy` field determines how the system calculates the resume date. Choose the appropriate policy based on your use case:

- **`SpecificDate`** - Use when you specify an exact resume date
- **`FixedPeriodsFromSuspendDate`** - Use when you want to resume after a calculated period from suspend date

### SpecificDate

Resume on a specific date. This is the most common policy for resume operations.

**Subscription API:**
```json
{
  "resumePolicy": "SpecificDate",
  "resumeSpecificDate": "2026-05-01"
}
```

**Order API:**
```json
{
  "resume": {
    "resumePolicy": "SpecificDate",
    "resumeSpecificDate": "2026-05-01"
  },
  "triggerDates": [{
    "name": "ContractEffective",
    "triggerDate": "2026-05-01"
  }]
}
```

**Note:** When using `SpecificDate`, you must specify both `resumeSpecificDate` in the resume object AND the date in `triggerDates`.

### FixedPeriodsFromSuspendDate

Resume after a fixed number of periods from the suspend date.

**Subscription API:**
```json
{
  "resumePolicy": "FixedPeriodsFromSuspendDate",
  "resumePeriods": 2,
  "resumePeriodsType": "Month"
}
```

**Order API:**
```json
{
  "resume": {
    "resumePolicy": "FixedPeriodsFromSuspendDate",
    "resumePeriods": 2,
    "resumePeriodsType": "Month"
  }
}
```

**Note:** `resumePeriods` and `resumePeriodsType` are required when using `FixedPeriodsFromSuspendDate`.

## Key Differences Summary

| Scenario | Subscription API | Order API |
|----------|------------------|-----------|
| Resume on specific date | Single call with `resumePolicy: "SpecificDate"`, `resumeSpecificDate` | Single Resume action with policy and specific date |
| Resume after period | `resumePolicy: "FixedPeriodsFromSuspendDate"` with periods | Same policy in Resume action |
| Term extension | `extendsTerm: true` at root level | `extendsTerm: true` in resume object |
| Multiple subscriptions | Multiple API calls | Single order with multiple subscriptions |

## Response Handling

### Subscription API Response

```json
{
  "success": true,
  "subscriptionId": "2c92a0fd...",
  "resumeDate": "2026-05-01",
  "totalDeltaMrr": 100.00
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
      "resumeDate": "2026-05-01"
    }
  ]
}
```

**Key Differences:**
- Order API returns `orderNumber` instead of just `subscriptionId`
- Order API includes full subscription details with status
- Order API response structure is consistent across all operations

## Migration Checklist

- [ ] Identify all subscription resume API calls in your code
- [ ] Update endpoint from `PUT /v1/subscriptions/{key}/resume` to `POST /v1/orders`
- [ ] Add required `orderDate` field
- [ ] Add required `existingAccountNumber` field
- [ ] Change `type` to `"Resume"`
- [ ] Wrap resume parameters in `resume` object
- [ ] When using `SpecificDate` policy, include both `resumeSpecificDate` in the resume object AND date in `triggerDates` array
- [ ] Nest actions in `orderActions` array
- [ ] Update response handling for new structure
- [ ] Test in sandbox environment

## Common Migration Patterns

### Pattern 1: Resume on Specific Date

**Before:**
```json
PUT /v1/subscriptions/A-S00000123/resume
{
  "resumeDate": "2026-05-01",
  "resumePolicy": "SpecificDate",
  "resumeSpecificDate": "2026-05-01",
  "extendsTerm": false
}
```

**After:**
```json
POST /v1/orders
{
  "orderDate": "2026-05-01",
  "existingAccountNumber": "A00000001",
  "subscriptions": [{
    "subscriptionNumber": "A-S00000123",
    "orderActions": [{
      "type": "Resume",
      "triggerDates": [{
        "name": "ContractEffective",
        "triggerDate": "2026-05-01"
      }],
      "resume": {
        "resumePolicy": "SpecificDate",
        "resumeSpecificDate": "2026-05-01",
        "extendsTerm": false
      }
    }]
  }]
}
```

### Pattern 2: Resume After Fixed Period

**Before:**
```json
PUT /v1/subscriptions/A-S00000123/resume
{
  "resumePolicy": "FixedPeriodsFromSuspendDate",
  "resumePeriods": 3,
  "resumePeriodsType": "Month"
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
      "type": "Resume",
      "resume": {
        "resumePolicy": "FixedPeriodsFromSuspendDate",
        "resumePeriods": 3,
        "resumePeriodsType": "Month"
      }
    }]
  }]
}
```

### Pattern 3: Resume Multiple Subscriptions

**Before (required multiple API calls):**
```json
PUT /v1/subscriptions/A-S00000123/resume
PUT /v1/subscriptions/A-S00000124/resume
```

**After (single API call):**
```json
POST /v1/orders
{
  "orderDate": "2026-05-01",
  "existingAccountNumber": "A00000001",
  "subscriptions": [
    {
      "subscriptionNumber": "A-S00000123",
      "orderActions": [{
        "type": "Resume",
        "triggerDates": [{
          "name": "ContractEffective",
          "triggerDate": "2026-05-01"
        }],
        "resume": {
          "resumePolicy": "SpecificDate",
          "resumeSpecificDate": "2026-05-01"
        }
      }]
    },
    {
      "subscriptionNumber": "A-S00000124",
      "orderActions": [{
        "type": "Resume",
        "triggerDates": [{
          "name": "ContractEffective",
          "triggerDate": "2026-05-01"
        }],
        "resume": {
          "resumePolicy": "SpecificDate",
          "resumeSpecificDate": "2026-05-01"
        }
      }]
    }
  ]
}
```

### Pattern 4: Resume with Term Extension

When you want the subscription term to be extended by the suspension duration.

**Before:**
```json
PUT /v1/subscriptions/A-S00000123/resume
{
  "contractEffectiveDate": "2026-04-21",
  "resumePolicy": "SpecificDate",
  "resumeSpecificDate": "2026-04-21",
  "extendsTerm": true
}
```

**After:**
```json
POST /v1/orders
{
  "orderDate": "2026-04-21",
  "existingAccountNumber": "A00000001",
  "subscriptions": [{
    "subscriptionNumber": "A-S00000123",
    "orderActions": [{
      "type": "Resume",
      "triggerDates": [{
        "name": "ContractEffective",
        "triggerDate": "2026-04-21"
      }],
      "resume": {
        "resumePolicy": "SpecificDate",
        "resumeSpecificDate": "2026-04-21",
        "extendsTerm": true
      }
    }]
  }]
}
```

**Note:** This is a common pattern when you want to ensure the customer gets the full subscription term they paid for, not losing any days during the suspension period.

## Benefits of Order API

1. **Bulk Operations**: Resume multiple subscriptions in one call
2. **Combined Actions**: Schedule resume with other order actions
3. **Better Tracking**: Order number for complete audit trail
4. **Consistency**: Same endpoint for all subscription modifications
5. **Future-Proof**: Order API is the strategic direction

## Important Notes

### extendsTerm Behavior

The `extendsTerm` field controls whether the subscription term should be extended by the **duration of the suspension period** (the gap between suspend and resume dates).

- `extendsTerm: true` - Extends the subscription term by the number of days the subscription was suspended
- `extendsTerm: false` - Keeps the original term end date unchanged

**Example:**
- Original term end date: Dec 31, 2026
- Suspend date: Apr 14, 2026
- Resume date: Apr 21, 2026
- Suspension duration: 7 days
- With `extendsTerm: true` → New term end: Jan 7, 2027 (extended by 7 days)
- With `extendsTerm: false` → Term end remains Dec 31, 2026

**Important for Order API Migration:**
- In **Subscription API**: `extendsTerm` is at the root level of the resume request
- In **Order API**: `extendsTerm` goes in the **resume object** within the Resume action
- This field is typically used to ensure customers don't lose subscription time during suspension

### Resume Period Calculation

When using `FixedPeriodsFromSuspendDate`:
- Suspend date + (resumePeriods × resumePeriodsType) = Resume date
- Example: Suspended on Apr 1 + 3 Months = Resume on Jul 1

### Subscription State Requirements

**Important:** You can only resume a subscription that is currently in a **Suspended** state.

- If the subscription is already Active, the resume call will fail
- Check the subscription status before attempting to resume
- Use the subscription GET API to verify current state

### Billing After Resume

- Upon resume, the subscription returns to Active status
- Charges will resume based on the subscription's rate plans
- The next invoice will include charges from the resume date forward
- Test in sandbox to verify billing behavior

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

**Error: Invalid resume policy**
```json
{
  "success": false,
  "reasons": [{
    "code": 53100040,
    "message": "Invalid resumePolicy value"
  }]
}
```
**Solution:** Use valid policy: `SpecificDate` or `FixedPeriodsFromSuspendDate`.

**Error: Subscription not suspended**
```json
{
  "success": false,
  "reasons": [{
    "code": 53100040,
    "message": "Cannot resume subscription that is not in Suspended state"
  }]
}
```
**Solution:** Verify the subscription is in Suspended state before attempting to resume.

**Error: Missing resume periods**
```json
{
  "success": false,
  "reasons": [{
    "code": 53100040,
    "message": "resumePeriods and resumePeriodsType are required for FixedPeriodsFromSuspendDate policy"
  }]
}
```
**Solution:** When using `FixedPeriodsFromSuspendDate`, include both `resumePeriods` and `resumePeriodsType`.

**Error: Missing resumeSpecificDate**
```json
{
  "success": false,
  "reasons": [{
    "code": 53100040,
    "message": "resumeSpecificDate is required when resumePolicy is SpecificDate"
  }]
}
```
**Solution:** When using `SpecificDate` policy, always include `resumeSpecificDate`.

## Related Operations

### Suspend and Resume in One Order

You can combine Suspend and Resume actions in a single order to schedule both operations at once:

```json
POST /v1/orders
{
  "orderDate": "2026-04-14",
  "existingAccountNumber": "A00000001",
  "subscriptions": [{
    "subscriptionNumber": "A-S00000123",
    "orderActions": [
      {
        "type": "Suspend",
        "triggerDates": [{
          "name": "ContractEffective",
          "triggerDate": "2026-04-14"
        }],
        "suspend": {
          "suspendPolicy": "SpecificDate",
          "suspendSpecificDate": "2026-04-14"
        }
      },
      {
        "type": "Resume",
        "triggerDates": [{
          "name": "ContractEffective",
          "triggerDate": "2026-04-21"
        }],
        "resume": {
          "resumePolicy": "SpecificDate",
          "resumeSpecificDate": "2026-04-21",
          "extendsTerm": false
        }
      }
    ]
  }]
}
```

This allows you to schedule a temporary suspension with a known end date in a single API call.

See the [Subscription Suspend API Migration Guide](amendment-rest-v1-suspend-api-mapping.md) for more details on suspend operations.

## Resources

- [Order API Documentation](https://www.zuora.com/developer/api-references/api/tag/Orders)
- [Subscription API Documentation](https://www.zuora.com/developer/api-references/api/tag/Subscriptions)
- [Resume Operation Guide](https://knowledgecenter.zuora.com/)
- [Subscription Suspend API Migration Guide](amendment-rest-v1-suspend-api-mapping.md)
