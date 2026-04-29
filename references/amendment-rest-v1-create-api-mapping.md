# Subscription Create API to Order API Migration Guide

Customer-facing guide for converting subscription creation operations from S/A API to Order API.

## Overview

This guide helps you migrate from the legacy Subscription Create API to the modern Order API.

The Subscription Create API allows you to:
- Create new subscriptions with product rate plans and charges
- Override rate plan and charge pricing
- Configure subscription terms (termed or evergreen)
- Set up auto-renewal behavior
- Customize charges across all charge models

### What You're Migrating

**FROM:** `POST /v1/subscriptions`

**TO:** `POST /v1/orders` with `CreateSubscription` action

## Quick Comparison

| Aspect | Subscription API | Order API |
|--------|------------------|-----------|
| Endpoint | `POST /v1/subscriptions` | `POST /v1/orders` |
| Action Type | Implicit (create) | Explicit (`CreateSubscription`) |
| Structure | Flat structure | Nested order action structure |
| Rate Plans | `subscribeToRatePlans[]` | `subscribeToRatePlans[]` |
| Charge Overrides | Nested in rate plan | Separate `chargeOverrides[]` array |
| Multiple Subscriptions | No (one per call) | Yes (multiple in one order) |

## Basic Subscription Creation

### Simple Subscription (No Overrides)

**Subscription API:**
```json
POST /v1/subscriptions
{
  "accountKey": "A00000001",
  "contractEffectiveDate": "2026-01-01",
  "termType": "TERMED",
  "initialTerm": 12,
  "initialTermPeriodType": "Month",
  "autoRenew": false,
  "renewalSetting": "RENEW_TO_EVERGREEN",
  "subscribeToRatePlans": [
    {
      "productRatePlanId": "2c92a0fe5a7d1234"
    }
  ]
}
```

**Order API:**
```json
POST /v1/orders
{
  "orderDate": "2026-01-01",
  "existingAccountNumber": "A00000001",
  "subscriptions": [
    {
      "orderActions": [
        {
          "type": "CreateSubscription",
          "createSubscription": {
            "terms": {
              "initialTerm": {
                "termType": "TERMED",
                "startDate": "2026-01-01",
                "period": 12,
                "periodType": "Month"
              },
              "autoRenew": false,
              "renewalSetting": "RENEW_TO_EVERGREEN"
            },
            "subscribeToRatePlans": [
              {
                "productRatePlanId": "2c92a0fe5a7d1234"
              }
            ]
          }
        }
      ]
    }
  ]
}
```

### Evergreen Subscription

**Subscription API:**
```json
POST /v1/subscriptions
{
  "accountKey": "A00000001",
  "contractEffectiveDate": "2026-01-01",
  "termType": "EVERGREEN",
  "subscribeToRatePlans": [
    {
      "productRatePlanId": "2c92a0fe5a7d1234"
    }
  ]
}
```

**Order API:**
```json
POST /v1/orders
{
  "orderDate": "2026-01-01",
  "existingAccountNumber": "A00000001",
  "subscriptions": [
    {
      "orderActions": [
        {
          "type": "CreateSubscription",
          "createSubscription": {
            "terms": {
              "initialTerm": {
                "termType": "EVERGREEN",
                "startDate": "2026-01-01"
              }
            },
            "subscribeToRatePlans": [
              {
                "productRatePlanId": "2c92a0fe5a7d1234"
              }
            ]
          }
        }
      ]
    }
  ]
}
```

## Field Mapping Table

### Top-Level Fields

| Subscription API Field | Order API Equivalent | Notes |
|------------------------|----------------------|-------|
| `accountKey` | `existingAccountNumber` | Account identifier |
| `contractEffectiveDate` | `createSubscription.terms.initialTerm.startDate` | Start date of the subscription |
| `termType` | `createSubscription.terms.initialTerm.termType` | Values: `TERMED`, `EVERGREEN` |
| `initialTerm` | `createSubscription.terms.initialTerm.period` | Length of initial term (for TERMED) |
| `initialTermPeriodType` | `createSubscription.terms.initialTerm.periodType` | Values: `Month`, `Year`, `Week`, `Day` |
| `autoRenew` | `createSubscription.terms.autoRenew` | Whether subscription auto-renews |
| `renewalSetting` | `createSubscription.terms.renewalSetting` | Values: `RENEW_WITH_SPECIFIC_TERM`, `RENEW_TO_EVERGREEN` |
| `renewalTerm` | `createSubscription.terms.renewalTerm` | Length of renewal term |
| `renewalTermPeriodType` | `createSubscription.terms.renewalTermPeriodType` | Period type for renewal |
| `subscribeToRatePlans[]` | `createSubscription.subscribeToRatePlans[]` | Product rate plans to subscribe to |
| `notes` | `createSubscription.notes` | Subscription notes |
| `subscriptionNumber` | `createSubscription.newSubscriptionNumber` | Custom subscription number |

### Rate Plan Fields

| Subscription API Field | Order API Equivalent | Notes |
|------------------------|----------------------|-------|
| `subscribeToRatePlans[].productRatePlanId` | `subscribeToRatePlans[].productRatePlanId` | Product rate plan identifier |
| `subscribeToRatePlans[].chargeOverrides[]` | `subscribeToRatePlans[].chargeOverrides[]` | Array of charge overrides |
| `subscribeToRatePlans[].customFields` | `subscribeToRatePlans[].ratePlanData` | Custom field overrides |

### Charge Override Fields

| Subscription API Field | Order API Equivalent | Notes |
|------------------------|----------------------|-------|
| `chargeOverrides[].productRatePlanChargeId` | `chargeOverrides[].productRatePlanChargeId` | Charge identifier |
| `chargeOverrides[].pricing` | `chargeOverrides[].pricing` | Pricing override structure |
| `chargeOverrides[].pricing.recurringFlatFee` | `chargeOverrides[].pricing.recurringFlatFee` | Flat fee pricing |
| `chargeOverrides[].pricing.recurringPerUnit` | `chargeOverrides[].pricing.recurringPerUnit` | Per unit pricing |
| `chargeOverrides[].pricing.recurringTiered` | `chargeOverrides[].pricing.recurringTiered` | Tiered pricing |
| `chargeOverrides[].pricing.recurringVolume` | `chargeOverrides[].pricing.recurringVolume` | Volume pricing |
| `chargeOverrides[].pricing.oneTimeFlatFee` | `chargeOverrides[].pricing.oneTimeFlatFee` | One-time flat fee |
| `chargeOverrides[].pricing.oneTimePerUnit` | `chargeOverrides[].pricing.oneTimePerUnit` | One-time per unit |
| `chargeOverrides[].pricing.oneTimeTiered` | `chargeOverrides[].pricing.oneTimeTiered` | One-time tiered |
| `chargeOverrides[].pricing.oneTimeVolume` | `chargeOverrides[].pricing.oneTimeVolume` | One-time volume |
| `chargeOverrides[].billingPeriod` | `chargeOverrides[].billing.billCycleDay` | Billing period override |
| `chargeOverrides[].triggerEvent` | `chargeOverrides[].chargeModel` | Trigger event for the charge |
| `chargeOverrides[].customFields` | `chargeOverrides[].chargeData` | Custom field overrides |

## Charge Model Overrides

The Order API supports all charge models with override capabilities. Here are detailed examples for each.

### Flat Fee Pricing

A fixed recurring charge regardless of quantity.

**Subscription API:**
```json
{
  "chargeOverrides": [
    {
      "productRatePlanChargeId": "2c92a0fe5a7d5678",
      "pricing": {
        "recurringFlatFee": {
          "listPrice": 100.00
        }
      }
    }
  ]
}
```

**Order API:**
```json
{
  "chargeOverrides": [
    {
      "productRatePlanChargeId": "2c92a0fe5a7d5678",
      "pricing": {
        "recurringFlatFee": {
          "listPrice": 100.00
        }
      }
    }
  ]
}
```

### Per Unit Pricing

Price per unit of quantity.

**Subscription API:**
```json
{
  "chargeOverrides": [
    {
      "productRatePlanChargeId": "2c92a0fe5a7d5678",
      "pricing": {
        "recurringPerUnit": {
          "listPrice": 10.00,
          "quantity": 5
        }
      }
    }
  ]
}
```

**Order API:**
```json
{
  "chargeOverrides": [
    {
      "productRatePlanChargeId": "2c92a0fe5a7d5678",
      "pricing": {
        "recurringPerUnit": {
          "listPrice": 10.00,
          "quantity": 5
        }
      }
    }
  ]
}
```

### Tiered Pricing

Different prices for different quantity tiers. The charge is the sum of all tier amounts.

**Subscription API:**
```json
{
  "chargeOverrides": [
    {
      "productRatePlanChargeId": "2c92a0fe5a7d5678",
      "pricing": {
        "recurringTiered": {
          "tiers": [
            {
              "tier": 1,
              "startingUnit": 1,
              "endingUnit": 10,
              "price": 10.00,
              "priceFormat": "Per Unit"
            },
            {
              "tier": 2,
              "startingUnit": 11,
              "endingUnit": 20,
              "price": 8.00,
              "priceFormat": "Per Unit"
            }
          ]
        }
      }
    }
  ]
}
```

**Order API:**
```json
{
  "chargeOverrides": [
    {
      "productRatePlanChargeId": "2c92a0fe5a7d5678",
      "pricing": {
        "recurringTiered": {
          "tiers": [
            {
              "tier": 1,
              "startingUnit": 1,
              "endingUnit": 10,
              "price": 10.00,
              "priceFormat": "Per Unit"
            },
            {
              "tier": 2,
              "startingUnit": 11,
              "endingUnit": 20,
              "price": 8.00,
              "priceFormat": "Per Unit"
            }
          ]
        }
      }
    }
  ]
}
```

**Pricing Formats:**
- `Per Unit` - Price × units in tier
- `Flat Fee` - Fixed price for the tier

**Example Calculation (15 units with Per Unit):**
- Tier 1: 10 units × $10 = $100
- Tier 2: 5 units × $8 = $40
- Total: $140

### Volume Pricing

Single price for all units based on total quantity.

**Subscription API:**
```json
{
  "chargeOverrides": [
    {
      "productRatePlanChargeId": "2c92a0fe5a7d5678",
      "pricing": {
        "recurringVolume": {
          "tiers": [
            {
              "tier": 1,
              "startingUnit": 1,
              "endingUnit": 10,
              "price": 10.00
            },
            {
              "tier": 2,
              "startingUnit": 11,
              "endingUnit": 20,
              "price": 8.00
            }
          ]
        }
      }
    }
  ]
}
```

**Order API:**
```json
{
  "chargeOverrides": [
    {
      "productRatePlanChargeId": "2c92a0fe5a7d5678",
      "pricing": {
        "recurringVolume": {
          "tiers": [
            {
              "tier": 1,
              "startingUnit": 1,
              "endingUnit": 10,
              "price": 10.00
            },
            {
              "tier": 2,
              "startingUnit": 11,
              "endingUnit": 20,
              "price": 8.00
            }
          ]
        }
      }
    }
  ]
}
```

**Example Calculation (15 units):**
- Falls in Tier 2 (11-20)
- All 15 units × $8 = $120

### One-Time Charges

**Flat Fee:**
```json
{
  "chargeOverrides": [
    {
      "productRatePlanChargeId": "2c92a0fe5a7d5678",
      "pricing": {
        "oneTimeFlatFee": {
          "listPrice": 50.00
        }
      }
    }
  ]
}
```

**Per Unit:**
```json
{
  "chargeOverrides": [
    {
      "productRatePlanChargeId": "2c92a0fe5a7d5678",
      "pricing": {
        "oneTimePerUnit": {
          "listPrice": 5.00,
          "quantity": 10
        }
      }
    }
  ]
}
```

### Discount Charges

**Fixed Amount Discount:**
```json
{
  "chargeOverrides": [
    {
      "productRatePlanChargeId": "2c92a0fe5a7d5678",
      "pricing": {
        "recurringFlatFee": {
          "listPrice": -10.00
        }
      },
      "discountLevel": "subscription"
    }
  ]
}
```

**Percentage Discount:**
```json
{
  "chargeOverrides": [
    {
      "productRatePlanChargeId": "2c92a0fe5a7d5678",
      "pricing": {
        "recurringPerUnit": {
          "listPrice": 0,
          "discountPercentage": 20
        }
      },
      "discountLevel": "subscription"
    }
  ]
}
```

## Complete Examples

### Example 1: Basic Termed Subscription

**Subscription API:**
```json
POST /v1/subscriptions
{
  "accountKey": "A00000001",
  "contractEffectiveDate": "2026-01-01",
  "termType": "TERMED",
  "initialTerm": 12,
  "initialTermPeriodType": "Month",
  "autoRenew": true,
  "renewalSetting": "RENEW_WITH_SPECIFIC_TERM",
  "renewalTerm": 12,
  "renewalTermPeriodType": "Month",
  "subscribeToRatePlans": [
    {
      "productRatePlanId": "2c92a0fe5a7d1234"
    }
  ]
}
```

**Order API:**
```json
POST /v1/orders
{
  "orderDate": "2026-01-01",
  "existingAccountNumber": "A00000001",
  "subscriptions": [
    {
      "orderActions": [
        {
          "type": "CreateSubscription",
          "createSubscription": {
            "terms": {
              "initialTerm": {
                "termType": "TERMED",
                "startDate": "2026-01-01",
                "period": 12,
                "periodType": "Month"
              },
              "autoRenew": true,
              "renewalSetting": "RENEW_WITH_SPECIFIC_TERM",
              "renewalTerm": 12,
              "renewalTermPeriodType": "Month"
            },
            "subscribeToRatePlans": [
              {
                "productRatePlanId": "2c92a0fe5a7d1234"
              }
            ]
          }
        }
      ]
    }
  ]
}
```

### Example 2: Subscription with Charge Overrides

**Subscription API:**
```json
POST /v1/subscriptions
{
  "accountKey": "A00000001",
  "contractEffectiveDate": "2026-01-01",
  "termType": "TERMED",
  "initialTerm": 12,
  "initialTermPeriodType": "Month",
  "subscribeToRatePlans": [
    {
      "productRatePlanId": "2c92a0fe5a7d1234",
      "chargeOverrides": [
        {
          "productRatePlanChargeId": "2c92a0fe5a7d5678",
          "pricing": {
            "recurringPerUnit": {
              "listPrice": 25.00,
              "quantity": 10
            }
          }
        },
        {
          "productRatePlanChargeId": "2c92a0fe5a7d9999",
          "pricing": {
            "oneTimeFlatFee": {
              "listPrice": 100.00
            }
          }
        }
      ]
    }
  ]
}
```

**Order API:**
```json
POST /v1/orders
{
  "orderDate": "2026-01-01",
  "existingAccountNumber": "A00000001",
  "subscriptions": [
    {
      "orderActions": [
        {
          "type": "CreateSubscription",
          "createSubscription": {
            "terms": {
              "initialTerm": {
                "termType": "TERMED",
                "startDate": "2026-01-01",
                "period": 12,
                "periodType": "Month"
              }
            },
            "subscribeToRatePlans": [
              {
                "productRatePlanId": "2c92a0fe5a7d1234",
                "chargeOverrides": [
                  {
                    "productRatePlanChargeId": "2c92a0fe5a7d5678",
                    "pricing": {
                      "recurringPerUnit": {
                        "listPrice": 25.00,
                        "quantity": 10
                      }
                    }
                  },
                  {
                    "productRatePlanChargeId": "2c92a0fe5a7d9999",
                    "pricing": {
                      "oneTimeFlatFee": {
                        "listPrice": 100.00
                      }
                    }
                  }
                ]
              }
            ]
          }
        }
      ]
    }
  ]
}
```

### Example 3: Multiple Rate Plans with Tiered Pricing

**Subscription API:**
```json
POST /v1/subscriptions
{
  "accountKey": "A00000001",
  "contractEffectiveDate": "2026-01-01",
  "termType": "EVERGREEN",
  "subscribeToRatePlans": [
    {
      "productRatePlanId": "2c92a0fe5a7d1234",
      "chargeOverrides": [
        {
          "productRatePlanChargeId": "2c92a0fe5a7d5678",
          "pricing": {
            "recurringTiered": {
              "tiers": [
                {
                  "tier": 1,
                  "startingUnit": 1,
                  "endingUnit": 100,
                  "price": 1.00,
                  "priceFormat": "Per Unit"
                },
                {
                  "tier": 2,
                  "startingUnit": 101,
                  "price": 0.75,
                  "priceFormat": "Per Unit"
                }
              ]
            }
          }
        }
      ]
    },
    {
      "productRatePlanId": "2c92a0fe5a7d4567"
    }
  ]
}
```

**Order API:**
```json
POST /v1/orders
{
  "orderDate": "2026-01-01",
  "existingAccountNumber": "A00000001",
  "subscriptions": [
    {
      "orderActions": [
        {
          "type": "CreateSubscription",
          "createSubscription": {
            "terms": {
              "initialTerm": {
                "termType": "EVERGREEN",
                "startDate": "2026-01-01"
              }
            },
            "subscribeToRatePlans": [
              {
                "productRatePlanId": "2c92a0fe5a7d1234",
                "chargeOverrides": [
                  {
                    "productRatePlanChargeId": "2c92a0fe5a7d5678",
                    "pricing": {
                      "recurringTiered": {
                        "tiers": [
                          {
                            "tier": 1,
                            "startingUnit": 1,
                            "endingUnit": 100,
                            "price": 1.00,
                            "priceFormat": "Per Unit"
                          },
                          {
                            "tier": 2,
                            "startingUnit": 101,
                            "price": 0.75,
                            "priceFormat": "Per Unit"
                          }
                        ]
                      }
                    }
                  }
                ]
              },
              {
                "productRatePlanId": "2c92a0fe5a7d4567"
              }
            ]
          }
        }
      ]
    }
  ]
}
```

## Code Examples

### Python - Create Basic Subscription

**Before (Subscription API):**
```python
import requests

url = "https://rest.zuora.com/v1/subscriptions"

payload = {
    "accountKey": "A00000001",
    "contractEffectiveDate": "2026-01-01",
    "termType": "TERMED",
    "initialTerm": 12,
    "initialTermPeriodType": "Month",
    "autoRenew": False,
    "subscribeToRatePlans": [
        {
            "productRatePlanId": "2c92a0fe5a7d1234"
        }
    ]
}

response = requests.post(url, json=payload, headers=headers)
```

**After (Order API):**
```python
import requests

url = "https://rest.zuora.com/v1/orders"

payload = {
    "orderDate": "2026-01-01",
    "existingAccountNumber": "A00000001",
    "subscriptions": [
        {
            "orderActions": [
                {
                    "type": "CreateSubscription",
                    "createSubscription": {
                        "terms": {
                            "initialTerm": {
                                "termType": "TERMED",
                                "startDate": "2026-01-01",
                                "period": 12,
                                "periodType": "Month"
                            },
                            "autoRenew": False
                        },
                        "subscribeToRatePlans": [
                            {
                                "productRatePlanId": "2c92a0fe5a7d1234"
                            }
                        ]
                    }
                }
            ]
        }
    ]
}

response = requests.post(url, json=payload, headers=headers)
```

### Python - Create with Charge Overrides

**Before (Subscription API):**
```python
import requests

url = "https://rest.zuora.com/v1/subscriptions"

payload = {
    "accountKey": "A00000001",
    "contractEffectiveDate": "2026-01-01",
    "termType": "EVERGREEN",
    "subscribeToRatePlans": [
        {
            "productRatePlanId": "2c92a0fe5a7d1234",
            "chargeOverrides": [
                {
                    "productRatePlanChargeId": "2c92a0fe5a7d5678",
                    "pricing": {
                        "recurringPerUnit": {
                            "listPrice": 25.00,
                            "quantity": 5
                        }
                    }
                }
            ]
        }
    ]
}

response = requests.post(url, json=payload, headers=headers)
```

**After (Order API):**
```python
import requests

url = "https://rest.zuora.com/v1/orders"

payload = {
    "orderDate": "2026-01-01",
    "existingAccountNumber": "A00000001",
    "subscriptions": [
        {
            "orderActions": [
                {
                    "type": "CreateSubscription",
                    "createSubscription": {
                        "terms": {
                            "initialTerm": {
                                "termType": "EVERGREEN",
                                "startDate": "2026-01-01"
                            }
                        },
                        "subscribeToRatePlans": [
                            {
                                "productRatePlanId": "2c92a0fe5a7d1234",
                                "chargeOverrides": [
                                    {
                                        "productRatePlanChargeId": "2c92a0fe5a7d5678",
                                        "pricing": {
                                            "recurringPerUnit": {
                                                "listPrice": 25.00,
                                                "quantity": 5
                                            }
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                }
            ]
        }
    ]
}

response = requests.post(url, json=payload, headers=headers)
```

### JavaScript - Create Subscription

**Before (Subscription API):**
```javascript
const url = 'https://rest.zuora.com/v1/subscriptions';

const payload = {
  accountKey: 'A00000001',
  contractEffectiveDate: '2026-01-01',
  termType: 'TERMED',
  initialTerm: 12,
  initialTermPeriodType: 'Month',
  subscribeToRatePlans: [
    {
      productRatePlanId: '2c92a0fe5a7d1234'
    }
  ]
};

const response = await fetch(url, {
  method: 'POST',
  headers: headers,
  body: JSON.stringify(payload)
});
```

**After (Order API):**
```javascript
const url = 'https://rest.zuora.com/v1/orders';

const payload = {
  orderDate: '2026-01-01',
  existingAccountNumber: 'A00000001',
  subscriptions: [
    {
      orderActions: [
        {
          type: 'CreateSubscription',
          createSubscription: {
            terms: {
              initialTerm: {
                termType: 'TERMED',
                startDate: '2026-01-01',
                period: 12,
                periodType: 'Month'
              }
            },
            subscribeToRatePlans: [
              {
                productRatePlanId: '2c92a0fe5a7d1234'
              }
            ]
          }
        }
      ]
    }
  ]
};

const response = await fetch(url, {
  method: 'POST',
  headers: headers,
  body: JSON.stringify(payload)
});
```

### Java - Create Subscription with Overrides

**Before (Subscription API):**
```java
String url = "https://rest.zuora.com/v1/subscriptions";

JSONObject payload = new JSONObject();
payload.put("accountKey", "A00000001");
payload.put("contractEffectiveDate", "2026-01-01");
payload.put("termType", "TERMED");
payload.put("initialTerm", 12);
payload.put("initialTermPeriodType", "Month");

JSONArray ratePlans = new JSONArray();
JSONObject ratePlan = new JSONObject();
ratePlan.put("productRatePlanId", "2c92a0fe5a7d1234");

JSONArray chargeOverrides = new JSONArray();
JSONObject chargeOverride = new JSONObject();
chargeOverride.put("productRatePlanChargeId", "2c92a0fe5a7d5678");

JSONObject pricing = new JSONObject();
JSONObject recurringPerUnit = new JSONObject();
recurringPerUnit.put("listPrice", 25.00);
recurringPerUnit.put("quantity", 5);
pricing.put("recurringPerUnit", recurringPerUnit);

chargeOverride.put("pricing", pricing);
chargeOverrides.put(chargeOverride);
ratePlan.put("chargeOverrides", chargeOverrides);
ratePlans.put(ratePlan);
payload.put("subscribeToRatePlans", ratePlans);

HttpPost request = new HttpPost(url);
request.setEntity(new StringEntity(payload.toString()));
HttpResponse response = httpClient.execute(request);
```

**After (Order API):**
```java
String url = "https://rest.zuora.com/v1/orders";

JSONObject payload = new JSONObject();
payload.put("orderDate", "2026-01-01");
payload.put("existingAccountNumber", "A00000001");

JSONArray subscriptions = new JSONArray();
JSONObject subscription = new JSONObject();

JSONArray orderActions = new JSONArray();
JSONObject orderAction = new JSONObject();
orderAction.put("type", "CreateSubscription");

JSONObject createSubscription = new JSONObject();

// Terms
JSONObject terms = new JSONObject();
JSONObject initialTerm = new JSONObject();
initialTerm.put("termType", "TERMED");
initialTerm.put("startDate", "2026-01-01");
initialTerm.put("period", 12);
initialTerm.put("periodType", "Month");
terms.put("initialTerm", initialTerm);
createSubscription.put("terms", terms);

// Rate Plans
JSONArray ratePlans = new JSONArray();
JSONObject ratePlan = new JSONObject();
ratePlan.put("productRatePlanId", "2c92a0fe5a7d1234");

JSONArray chargeOverrides = new JSONArray();
JSONObject chargeOverride = new JSONObject();
chargeOverride.put("productRatePlanChargeId", "2c92a0fe5a7d5678");

JSONObject pricing = new JSONObject();
JSONObject recurringPerUnit = new JSONObject();
recurringPerUnit.put("listPrice", 25.00);
recurringPerUnit.put("quantity", 5);
pricing.put("recurringPerUnit", recurringPerUnit);

chargeOverride.put("pricing", pricing);
chargeOverrides.put(chargeOverride);
ratePlan.put("chargeOverrides", chargeOverrides);
ratePlans.put(ratePlan);
createSubscription.put("subscribeToRatePlans", ratePlans);

orderAction.put("createSubscription", createSubscription);
orderActions.put(orderAction);
subscription.put("orderActions", orderActions);
subscriptions.put(subscription);
payload.put("subscriptions", subscriptions);

HttpPost request = new HttpPost(url);
request.setEntity(new StringEntity(payload.toString()));
HttpResponse response = httpClient.execute(request);
```

## Response Handling

### Subscription API Response

```json
{
  "success": true,
  "subscriptionId": "2c92a0fd...",
  "subscriptionNumber": "A-S00000123",
  "totalContractedValue": 1200.00,
  "invoiceId": "2c92a0fe...",
  "invoiceNumber": "INV00000001"
}
```

### Order API Response

```json
{
  "success": true,
  "orderNumber": "O-00001234",
  "accountNumber": "A00000001",
  "status": "Completed",
  "subscriptions": [
    {
      "subscriptionNumber": "A-S00000123",
      "status": "Active",
      "subscriptionId": "2c92a0fd...",
      "invoiceId": "2c92a0fe...",
      "invoiceNumber": "INV00000001",
      "totalContractedValue": 1200.00
    }
  ]
}
```

**Key Differences:**
- Order API returns `orderNumber` for tracking
- Order API provides comprehensive subscription details
- Order API status indicates processing state
- Order API response structure is consistent across operations

## Migration Checklist

- [ ] Identify all subscription create API calls in your code
- [ ] Map `accountKey` to `existingAccountNumber`
- [ ] Update endpoint from `POST /v1/subscriptions` to `POST /v1/orders`
- [ ] Add required `orderDate` field
- [ ] Wrap subscription data in `createSubscription` object
- [ ] Nest `createSubscription` in `orderActions[]` array
- [ ] Map term fields to `terms.initialTerm` structure
- [ ] Keep `subscribeToRatePlans` field name (same in Order API)
- [ ] Verify charge override structure (should remain similar)
- [ ] Update response handling for new structure
- [ ] Test all charge model overrides (flat fee, per unit, tiered, volume)
- [ ] Verify custom field mappings
- [ ] Test in sandbox environment

## Key Differences Summary

| Scenario | Subscription API | Order API |
|----------|------------------|-----------|
| Basic creation | Flat structure with `subscribeToRatePlans` | Nested in `createSubscription` action |
| Rate plans | `subscribeToRatePlans[]` | `subscribeToRatePlans[]` |
| Charge overrides | Nested in rate plan | Same structure in `chargeOverrides[]` |
| Terms | Root-level fields | Nested in `terms.initialTerm` |
| Multiple subscriptions | Multiple API calls | Single order with multiple subscription actions |

## Benefits of Order API

1. **Atomic Operations**: Create multiple subscriptions in one transaction
2. **Better Tracking**: Order number for complete audit trail
3. **Combined Actions**: Mix subscription creation with other operations
4. **Consistency**: Same endpoint for all subscription modifications
5. **Enhanced Flexibility**: More granular control over pricing and terms
6. **Future-Proof**: Order API is the strategic direction

## Important Notes

### Term Types

- **TERMED**: Fixed-length subscription with defined start and end dates
- **EVERGREEN**: Ongoing subscription with no end date

### Auto-Renewal Settings

- `autoRenew: true` - Subscription automatically renews at term end
- `autoRenew: false` - Subscription ends at term end
- `renewalSetting: "RENEW_WITH_SPECIFIC_TERM"` - Renew with specific term length
- `renewalSetting: "RENEW_TO_EVERGREEN"` - Convert to evergreen on renewal

### Charge Override Requirements

When overriding charges, you must:
1. Specify the `productRatePlanChargeId`
2. Provide complete pricing information for the charge model
3. Match the pricing structure to the charge model type (flat fee, per unit, tiered, etc.)

### Rate Plan vs Charge Overrides

- **Rate Plan Data**: Custom fields and metadata for the rate plan
- **Charge Overrides**: Pricing, quantity, and charge-specific settings

### Tiered vs Volume Pricing

- **Tiered**: Charge accumulates across tiers (sum of all tier amounts)
- **Volume**: All units charged at the price of the tier they fall into

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

**Error: Invalid term type**
```json
{
  "success": false,
  "reasons": [{
    "code": 53100040,
    "message": "Invalid termType value"
  }]
}
```
**Solution:** Use valid term type: `TERMED` or `EVERGREEN`.

**Error: Invalid charge override**
```json
{
  "success": false,
  "reasons": [{
    "code": 53100040,
    "message": "Charge override pricing must match charge model type"
  }]
}
```
**Solution:** Ensure pricing structure matches the charge's model (e.g., don't use `recurringFlatFee` for a per-unit charge).

**Error: Missing rate plan**
```json
{
  "success": false,
  "reasons": [{
    "code": 53100040,
    "message": "At least one product rate plan is required"
  }]
}
```
**Solution:** Include at least one product in `subscribeToRatePlans[]` array.

## Resources

- [Order API Documentation](https://www.zuora.com/developer/api-references/api/tag/Orders)
- [Subscription API Documentation](https://www.zuora.com/developer/api-references/api/tag/Subscriptions)
- [Charge Models Guide](https://knowledgecenter.zuora.com/)
- [Product Catalog Overview](https://knowledgecenter.zuora.com/)
