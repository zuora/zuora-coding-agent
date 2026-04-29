# Subscription Suspend API to Order API Migration Guide

Customer-facing guide for converting subscription suspend operations from S/A API to Order API.

## Overview

This guide helps you migrate from the legacy Subscription Suspend API to the modern Order API.

The Subscription Suspend API allows you to:
- Suspend a subscription with or without a specific resume date
- **Suspend and resume a subscription in a single API call** by specifying both suspend and resume parameters

### What You're Migrating

**FROM:** `PUT /v1/subscriptions/{subscription-key}/suspend`
- Can specify suspend parameters only
- Can specify both suspend AND resume parameters in the same call

**TO:** `POST /v1/orders`
- For suspend only: Single `Suspend` action
- For suspend + resume: Both `Suspend` and `Resume` actions in the same order

### Key Architectural Difference: Subscription Versions

**Subscription API** creates multiple subscription versions:
- Suspend + Resume = **2 subscription versions**
- Suspend + Resume + `extendsTerm: true` = **3 subscription versions** (third version is a TermsAndConditions amendment to change term length)

**Order API** consolidates actions into fewer versions:
- Suspend + Resume = **2 order actions**, but only **1 new subscription version**
- Suspend + Resume + `extendsTerm: true` = **3 order actions** (Suspend, Resume, TermsAndConditions), but still only **1 new subscription version**

This means Order API is more efficient in managing subscription version history.

## Quick Comparison

| Aspect | Subscription API | Order API |
|--------|------------------|-----------|
| Endpoint | `PUT /v1/subscriptions/{sub-key}/suspend` | `POST /v1/orders` |
| Action Type | Implicit (suspend) | Explicit (`Suspend`, `Resume`) |
| Multiple Subscriptions | No (one per call) | Yes (one order can affect multiple subs) |
| Suspend + Resume | Creates 2 subscription versions | Creates 2 order actions, 1 subscription version |
| Suspend + Resume + extendsTerm | Creates 3 subscription versions | Creates 3 order actions, 1 subscription version |
| Complexity | Simple | More flexible and efficient |

## Suspend API Field Mapping

### Basic Suspend Request (Suspend Only)

**Subscription API:**
```json
PUT /v1/subscriptions/A-S00000123/suspend
{
  "suspendDate": "2026-09-01",
  "contractEffectiveDate": "2026-09-01",
  "suspendPolicy": "FixedPeriodsFromToday",
  "suspendPeriods": 3,
  "suspendPeriodsType": "Month"
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
          "type": "Suspend",
          "triggerDates": [
            {
              "name": "ContractEffective",
              "triggerDate": "2026-09-01"
            }
          ],
          "suspend": {
            "suspendPolicy": "FixedPeriodsFromToday",
            "suspendPeriods": "3",
            "suspendPeriodsType": "Month"
          }
        }
      ]
    }
  ]
}
```

### Suspend with Resume Date (Single Call)

The Suspend API allows you to specify both suspend and resume dates in a single call.

**Subscription API:**
```json
PUT /v1/subscriptions/A-S00000123/suspend
{
  "contractEffectiveDate": "2026-04-14",
  "suspendPolicy": "SpecificDate",
  "suspendSpecificDate": "2026-04-14",
  "resumePolicy": "SpecificDate",
  "resumeSpecificDate": "2026-04-21",
  "extendsTerm": false
}
```

**Order API:**
```json
POST /v1/orders
{
  "orderDate": "2026-04-14",
  "existingAccountNumber": "A00000001",
  "subscriptions": [
    {
      "subscriptionNumber": "A-S00000123",
      "orderActions": [
        {
          "type": "Suspend",
          "triggerDates": [
            {
              "name": "ContractEffective",
              "triggerDate": "2026-04-14"
            }
          ],
          "suspend": {
            "suspendPolicy": "SpecificDate",
            "suspendSpecificDate": "2026-04-14"
          }
        },
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
            "extendsTerm": false
          }
        }
      ]
    }
  ]
}
```

**Key Differences:** 
- In Order API, you specify **two separate actions** (Suspend and Resume) within the same order to achieve suspend + resume in a single call
- The `extendsTerm` field moves from the Subscription API root level to the **Resume action** in Order API
- **Version efficiency**: Subscription API creates 2 subscription versions (suspend + resume), but Order API creates only 1 subscription version with 2 order actions

### Suspend Field Mapping Table

| Subscription Suspend Field | Order API Equivalent | Notes |
|---------------------------|----------------------|-------|
| `contractEffectiveDate` | `triggerDates[].triggerDate` | Primary trigger date for both Suspend and Resume actions |
| `suspendPolicy` | `subscriptions[].orderActions[].suspend.suspendPolicy` | Values: `FixedPeriodsFromToday`, `EndOfLastInvoicePeriod`, `SpecificDate` |
| `suspendSpecificDate` | `subscriptions[].orderActions[].suspend.suspendSpecificDate`  | Required when `suspendPolicy` is `SpecificDate` |
| `suspendPeriods` | `subscriptions[].orderActions[].suspend.suspendPeriods` | Number of periods to suspend |
| `suspendPeriodsType` | `subscriptions[].orderActions[].suspend.suspendPeriodsType` | Values: `Day`, `Week`, `Month`, `Year` |
| `resumePolicy` | `subscriptions[].orderActions[].resume.resumePolicy` | Add a separate Resume action. Set to `SpecificDate` when using specific resume date |
| `resumeSpecificDate` | `subscriptions[].orderActions[].resume.resumeSpecificDate` | Required when `resumePolicy` is `SpecificDate` |
| `extendsTerm` | `subscriptions[].orderActions[].resume.extendsTerm` | Extends subscription term by the suspension duration (gap between suspend and resume). Goes in the **Resume action**, not Suspend |
| N/A (implicit in URL) | `subscriptionNumber` | Now in request body |
| N/A (from subscription) | `existingAccountNumber` | Required field |

### New Required Fields

Order API requires these additional fields:

- `orderDate` - The date of the order
- `existingAccountNumber` - The account number
- `subscriptionNumber` - Inside subscriptions array (was in URL path)

## Code Examples

### Python - Suspend Subscription

**Before (Subscription API):**
```python
import requests

subscription_key = "A-S00000123"
url = "https://rest.zuora.com/v1/subscriptions/{subscription_key}/suspend"

payload = {
    "suspendDate": "2026-09-01",
    "suspendPolicy": "FixedPeriodsFromToday",
    "suspendPeriods": 3,
    "suspendPeriodsType": "Month"
}

response = requests.put(url, json=payload, headers=headers)
```

**After (Order API):**
```python
import requests

url = "https://rest.zuora.com/v1/orders"

payload = {
    "orderDate": "2026-09-01",
    "existingAccountNumber": "A00000001",  # NEW: Required
    "subscriptions": [{
        "subscriptionNumber": "A-S00000123",
        "orderActions": [{
            "type": "Suspend",
            "triggerDates": [{
                "name": "ContractEffective",
                "triggerDate": "2026-09-01"
            }],
            "suspend": {
                "suspendPolicy": "FixedPeriodsFromToday",
                "suspendPeriods": "3",
                "suspendPeriodsType": "Month"
            }
        }]
    }]
}

response = requests.post(url, json=payload, headers=headers)
```

### Python - Suspend with Resume Date

**Before (Subscription API):**
```python
import requests

subscription_key = "A-S00000123"
url = f"https://rest.zuora.com/v1/subscriptions/{subscription_key}/suspend"

payload = {
    "contractEffectiveDate": "2026-04-14",
    "suspendPolicy": "SpecificDate",
    "suspendSpecificDate": "2026-04-14",
    "resumePolicy": "SpecificDate",
    "resumeSpecificDate": "2026-04-21",  # Resume after 1 week
    "extendsTerm": False
}

response = requests.put(url, json=payload, headers=headers)
```

**After (Order API):**
```python
import requests

url = "https://rest.zuora.com/v1/orders"

payload = {
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
                    "extendsTerm": False
                }
            }
        ]
    }]
}

response = requests.post(url, json=payload, headers=headers)
```

### Java - Suspend Subscription

**Before (Subscription API):**
```java
String subscriptionKey = "A-S00000123";
String url = "https://rest.zuora.com/v1/subscriptions/" + subscriptionKey + "/suspend";

JSONObject payload = new JSONObject();
payload.put("suspendDate", "2026-09-01");
payload.put("suspendPolicy", "FixedPeriodsFromToday");
payload.put("suspendPeriods", 3);
payload.put("suspendPeriodsType", "Month");
payload.put("extendsTerm", true);

HttpPut request = new HttpPut(url);
request.setEntity(new StringEntity(payload.toString()));
HttpResponse response = httpClient.execute(request);
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
action.put("type", "Suspend");

JSONArray triggerDates = new JSONArray();
JSONObject triggerDate = new JSONObject();
triggerDate.put("name", "ContractEffective");
triggerDate.put("triggerDate", "2026-09-01");
triggerDates.put(triggerDate);
action.put("triggerDates", triggerDates);

JSONObject suspend = new JSONObject();
suspend.put("suspendPolicy", "FixedPeriodsFromToday");
suspend.put("suspendPeriods", "3");
suspend.put("suspendPeriodsType", "Month");
suspend.put("extendsTerm", true);
action.put("suspend", suspend);

orderActions.put(action);
subscription.put("orderActions", orderActions);
subscriptions.put(subscription);
payload.put("subscriptions", subscriptions);

HttpPost request = new HttpPost(url);
request.setEntity(new StringEntity(payload.toString()));
HttpResponse response = httpClient.execute(request);
```

### JavaScript - Suspend Subscription

**Before (Subscription API):**
```javascript
const subscriptionKey = 'A-S00000123';
const url = `https://rest.zuora.com/v1/subscriptions/${subscriptionKey}/suspend`;

const payload = {
  suspendDate: '2026-09-01',
  suspendPolicy: 'EndOfLastInvoicePeriod'
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
      type: 'Suspend',
      triggerDates: [{
        name: 'ContractEffective',
        triggerDate: '2026-09-01'
      }],
      suspend: {
        suspendPolicy: 'EndOfLastInvoicePeriod'
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

### JavaScript - Suspend with Resume Date

**Before (Subscription API):**
```javascript
const subscriptionKey = 'A-S00000123';
const url = `https://rest.zuora.com/v1/subscriptions/${subscriptionKey}/suspend`;

const payload = {
  contractEffectiveDate: '2026-04-14',
  suspendPolicy: 'SpecificDate',
  suspendSpecificDate: '2026-04-14',
  resumePolicy: 'SpecificDate',
  resumeSpecificDate: '2026-04-21',  // Resume after 1 week
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
  orderDate: '2026-04-14',
  existingAccountNumber: 'A00000001',
  subscriptions: [{
    subscriptionNumber: 'A-S00000123',
    orderActions: [
      {
        type: 'Suspend',
        triggerDates: [{
          name: 'ContractEffective',
          triggerDate: '2026-04-14'
        }],
        suspend: {
          suspendPolicy: 'SpecificDate',
          suspendSpecificDate: '2026-04-14'
        }
      },
      {
        type: 'Resume',
        triggerDates: [{
          name: 'ContractEffective',
          triggerDate: '2026-04-21'
        }],
        resume: {
          resumePolicy: 'SpecificDate',
          resumeSpecificDate: '2026-04-21',
          extendsTerm: false
        }
      }
    ]
  }]
};

const response = await fetch(url, {
  method: 'POST',
  headers: headers,
  body: JSON.stringify(payload)
});
```

## Suspend Policies

The `suspendPolicy` field determines how the system calculates suspend and resume dates. Choose the appropriate policy based on your use case:

- **`SpecificDate`** - Use when you specify exact suspend/resume dates
- **`FixedPeriodsFromToday`** - Use when you want to suspend for a calculated period (e.g., "3 months from today")
- **`EndOfLastInvoicePeriod`** - Use when you want to align suspension with billing periods

### FixedPeriodsFromToday

Suspend for a fixed number of periods from the suspend date.

**Subscription API:**
```json
{
  "suspendPolicy": "FixedPeriodsFromToday",
  "suspendPeriods": 3,
  "suspendPeriodsType": "Month"
}
```

**Order API:**
```json
{
  "suspend": {
    "suspendPolicy": "FixedPeriodsFromToday",
    "suspendPeriods": "3",
    "suspendPeriodsType": "Month"
  }
}
```

**Note:** `suspendPeriods` and `suspendPeriodsType` are required when using `FixedPeriodsFromToday`.

### EndOfLastInvoicePeriod

Suspend at the end of the last invoice period.

**Subscription API:**
```json
{
  "suspendPolicy": "EndOfLastInvoicePeriod"
}
```

**Order API:**
```json
{
  "suspend": {
    "suspendPolicy": "EndOfLastInvoicePeriod"
  }
}
```

### SpecificDate

Suspend on a specific date. Use this policy when you specify exact suspend/resume dates.

**Subscription API:**
```json
{
  "suspendPolicy": "SpecificDate",
  "suspendSpecificDate": "2026-09-01"
}
```

**Order API:**
```json
{
  "suspend": {
    "suspendPolicy": "SpecificDate",
    "suspendSpecificDate": "2026-09-01"
  },
  "triggerDates": [{
    "name": "ContractEffective",
    "triggerDate": "2026-09-01"
  }]
}
```

**Note:** When using `SpecificDate`, you must specify both `suspendSpecificDate` in the suspend object AND the date in `triggerDates`. If you also specify a resume date, set `resumePolicy: "SpecificDate"` and `resumeSpecificDate` in the Resume action.

## Key Differences Summary

| Aspect | Subscription API | Order API |
|--------|------------------|-----------|
| **API Structure** | | |
| Suspend only | Single call with `suspendPolicy` | Single Suspend action |
| Suspend with resume | Single call with `suspendSpecificDate`, `resumeSpecificDate`, `suspendPolicy: "SpecificDate"`, `resumePolicy: "SpecificDate"` | Two actions: Suspend + Resume, both with policy and specific dates |
| Suspend for period | `suspendPolicy: "FixedPeriodsFromToday"` with periods | Same policy in Suspend action |
| Term extension | `extendsTerm: true` at root level | `extendsTerm: true` in **resume** object (not suspend) |
| **Subscription Versions** | | |
| Suspend + Resume | Creates **2 new versions** | Creates **1 new version** with 2 order actions |
| Suspend + Resume + extendsTerm | Creates **3 new versions** (suspend, resume, terms amendment) | Creates **1 new version** with 3 order actions |

## Response Handling

### Subscription API Response

```json
{
  "success": true,
  "subscriptionId": "2c92a0fd...",
  "suspendDate": "2026-09-01",
  "resumeDate": "2026-12-01",
  "totalDeltaMrr": 0.00
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
      "status": "Suspended",
      "suspendDate": "2026-09-01",
      "resumeDate": "2026-12-01"
    }
  ]
}
```

**Key Differences:**
- Order API returns `orderNumber` instead of just `subscriptionId`
- Order API includes full subscription details with status
- Order API response structure is consistent across all operations

## Migration Checklist

- [ ] Identify all subscription suspend API calls in your code
- [ ] Check if any calls include `resumeSpecificDate`/`resumePolicy` (requires two order actions: Suspend + Resume)
- [ ] Update endpoint from `PUT /v1/subscriptions/{key}/suspend` to `POST /v1/orders`
- [ ] Add required `orderDate` field
- [ ] Add required `existingAccountNumber` field
- [ ] Change `type` to `"Suspend"`
- [ ] If `resumeSpecificDate` exists, add a second order action with `type` = `"Resume"` including `resumePolicy` and `resumeSpecificDate`
- [ ] Wrap suspend parameters in `suspend` object
- [ ] When using `SpecificDate` policy, include both `suspendSpecificDate`/`resumeSpecificDate` in the action object AND dates in `triggerDates` array
- [ ] Nest actions in `orderActions` array
- [ ] Update response handling for new structure
- [ ] Test in sandbox environment

## Common Migration Patterns

### Pattern 1: Simple Suspend at End of Invoice Period

**Before:**
```json
PUT /v1/subscriptions/A-S00000123/suspend
{
  "suspendPolicy": "EndOfLastInvoicePeriod"
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
      "type": "Suspend",
      "suspend": {
        "suspendPolicy": "EndOfLastInvoicePeriod"
      }
    }]
  }]
}
```

### Pattern 2: Suspend for Fixed Period

**Before:**
```json
PUT /v1/subscriptions/A-S00000123/suspend
{
  "suspendPolicy": "FixedPeriodsFromToday",
  "suspendPeriods": 6,
  "suspendPeriodsType": "Month"
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
      "type": "Suspend",
      "suspend": {
        "suspendPolicy": "FixedPeriodsFromToday",
        "suspendPeriods": "6",
        "suspendPeriodsType": "Month"
      }
    }]
  }]
}
```

### Pattern 3: Suspend Multiple Subscriptions

**Before (required multiple API calls):**
```json
PUT /v1/subscriptions/A-S00000123/suspend
PUT /v1/subscriptions/A-S00000124/suspend
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
      "orderActions": [{
        "type": "Suspend",
        "suspend": {"suspendPolicy": "EndOfLastInvoicePeriod"}
      }]
    },
    {
      "subscriptionNumber": "A-S00000124",
      "orderActions": [{
        "type": "Suspend",
        "suspend": {"suspendPolicy": "EndOfLastInvoicePeriod"}
      }]
    }
  ]
}
```

### Pattern 4: Suspend with Known Resume Date

When both suspend and resume dates are known (common use case).

**Before:**
```json
PUT /v1/subscriptions/A-S00000123/suspend
{
  "contractEffectiveDate": "2026-04-14",
  "suspendPolicy": "SpecificDate",
  "suspendSpecificDate": "2026-04-14",
  "resumePolicy": "SpecificDate",
  "resumeSpecificDate": "2026-04-21",
  "extendsTerm": false
}
```

**After:**
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

**Note:** This is one of the most common patterns - suspending for a known period (e.g., vacation, temporary service pause). 

Key observations:
- The suspension duration is 7 days
- If `extendsTerm: true` (in the Resume action), the subscription term would be extended by 7 days, which creates an additional TermsAndConditions order action
- **Subscription API** would create **2 versions** for this operation; **Order API** creates only **1 version** with 2 order actions

## Benefits of Order API

1. **Fewer Subscription Versions**: Order API creates fewer subscription versions compared to Subscription API, simplifying version history
   - Suspend + Resume: 1 version vs. 2 versions in Subscription API
   - Suspend + Resume + extendsTerm: 1 version vs. 3 versions in Subscription API
2. **Bulk Operations**: Suspend multiple subscriptions in one call
3. **Combined Actions**: Schedule suspend with other order actions in the same order
4. **Better Tracking**: Order number for complete audit trail across all actions
5. **Consistency**: Same endpoint for all subscription modifications
6. **Future-Proof**: Order API is the strategic direction

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
- In **Subscription API**: `extendsTerm` is at the root level of the suspend request
- In **Order API**: `extendsTerm` goes in the **Resume action** (`resume` object), NOT in the Suspend action
- If you have a suspend-only operation (no resume date), `extendsTerm` will be applied when the subscription is resumed later

**How extendsTerm Works:**

When `extendsTerm: true` is set:

- **Subscription API**: Creates a separate **TermsAndConditions amendment** as a third subscription version to change the term length
- **Order API**: Creates a **TermsAndConditions order action** along with Suspend and Resume actions, all consolidated into one subscription version

Example with `extendsTerm: true`:
- Subscription API: 3 separate versions (Suspend → Resume → TermsAndConditions)
- Order API: 3 order actions, but 1 version (Suspend + Resume + TermsAndConditions)

### Suspend Period Calculation

When using `FixedPeriodsFromToday`:
- Suspend date + (suspendPeriods × suspendPeriodsType) = Resume date
- Example: Suspend on Apr 1 + 3 Months = Resume on Jul 1

### Specifying Resume Date

You have two options for controlling when a subscription resumes:

**Option 1: Use `resumeSpecificDate` field with `resumePolicy: "SpecificDate"` (Subscription API)**
- Specify exact resume date in the suspend call
- Requires setting `resumePolicy: "SpecificDate"`
- Maps to separate Resume action in Order API with `resumePolicy` and `resumeSpecificDate`
- Best for known resume dates (e.g., vacation period, seasonal pause)

**Option 2: Use `suspendPolicy` with periods**
- System calculates resume date automatically
- Use `FixedPeriodsFromToday` with `suspendPeriods` and `suspendPeriodsType`
- Best for relative time periods (e.g., "suspend for 3 months")

### Billing During Suspension

- Suspended subscriptions typically don't generate charges
- Depends on your rate plan configuration
- Test in sandbox to verify billing behavior

## Order Actions vs Subscription Versions

Understanding how actions and versions are created is crucial for migration planning.

### Subscription API Behavior

The Subscription Suspend API creates a **new subscription version for each state change**:

**Scenario 1: Suspend + Resume (without extendsTerm)**
1. Call suspend with resume
2. Creates **Version 2**: Suspended state
3. Creates **Version 3**: Active state (resume)
4. **Total: 2 new versions**

**Scenario 2: Suspend + Resume + extendsTerm=true**
1. Call suspend with resume and `extendsTerm: true`
2. Creates **Version 2**: Suspended state
3. Creates **Version 3**: Active state (resume)
4. Creates **Version 4**: TermsAndConditions amendment to extend term length
5. **Total: 3 new versions**

### Order API Behavior

The Order API creates **multiple order actions but consolidates into fewer subscription versions**:

**Scenario 1: Suspend + Resume (without extendsTerm)**
1. Single order with 2 actions: Suspend + Resume
2. Creates **2 order actions**: `SuspendSubscription` and `ResumeSubscription`
3. Creates **1 new subscription version** containing both changes
4. **Total: 1 new version** (vs. 2 in Subscription API)

**Scenario 2: Suspend + Resume + extendsTerm=true**
1. Single order with 3 actions: Suspend + Resume (with extendsTerm)
2. Creates **3 order actions**: `SuspendSubscription`, `ResumeSubscription`, and `TermsAndConditions`
3. Creates **1 new subscription version** containing all changes
4. **Total: 1 new version** (vs. 3 in Subscription API)

### Why This Matters

**Version History Clarity:**
- Fewer versions mean cleaner subscription history
- Easier to track and audit changes
- Reduced database overhead

**Rollback Considerations:**
- Subscription API: Each version can be individually identified
- Order API: Multiple actions are bundled into one version

**Reporting and Analytics:**
- Version counts will differ between the two APIs
- Ensure reporting tools account for this difference

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

**Error: Invalid suspend policy**
```json
{
  "success": false,
  "reasons": [{
    "code": 53100040,
    "message": "Invalid suspendPolicy value"
  }]
}
```
**Solution:** Use valid policy: `FixedPeriodsFromToday`, `EndOfLastInvoicePeriod`, or `SpecificDate`.

**Error: Missing suspend periods**
```json
{
  "success": false,
  "reasons": [{
    "code": 53100040,
    "message": "suspendPeriods and suspendPeriodsType are required for FixedPeriodsFromToday policy"
  }]
}
```
**Solution:** When using `FixedPeriodsFromToday`, include both `suspendPeriods` and `suspendPeriodsType`.

## Resources

- [Order API Documentation](https://www.zuora.com/developer/api-references/api/tag/Orders)
- [Subscription API Documentation](https://www.zuora.com/developer/api-references/api/tag/Subscriptions)
- [Suspend Operation Guide](https://knowledgecenter.zuora.com/)
