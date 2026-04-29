# Subscription Update API to Order API Migration Guide

Customer-facing guide for converting subscription update operations from S/A API to Order API.

## Overview

This guide helps you migrate from the legacy Subscription Update API to the modern Order API.

The Subscription Update API is the most complex subscription operation, allowing you to perform multiple types of amendments in a single API call:
- **Add** product rate plans to a subscription
- **Update** existing product charges
- **Remove** product rate plans from a subscription
- **Change** product rate plans (upgrade/downgrade)
- **Modify terms and conditions** (renewal settings, term lengths, auto-renewal)
- **Update custom fields** only (without any amendments)

### What You're Migrating

**FROM:** `PUT /v1/subscriptions/{subscription-key}`

**TO:** `POST /v1/orders` with multiple order action types

## Quick Comparison

| Aspect | Subscription API | Order API                                                                                                  |
|--------|------------------|------------------------------------------------------------------------------------------------------------|
| Endpoint | `PUT /v1/subscriptions/{key}` | `POST /v1/orders`                                                                                          |
| Action Types | `add`, `update`, `remove`, `change`, `termsAndConditions` | Explicit order actions: `AddProduct`, `UpdateProduct`, `RemoveProduct`, `ChangePlan`, `TermsAndConditions` |
| Action Sequence | Fixed by type (not customer-controlled) | Customer-controlled sequence via `orderActions[]` array                                                    |
| Action Limit | Default: max 9 add+update+remove+change (configurable) | Sync: max 50 actions, Async: max 300 actions                                                               |
| Versioning | Each amendment creates one new version | All order actions in one order create ONE version only                                              |
| Terms Changes | Root-level fields | Explicit `TermsAndConditions` action                                                                       |
| Custom Fields Only | Root-level `customFieldsData` only | Update subscription custom fields via order                                                                |
| Multiple Subscriptions | No (one per call) | Yes (multiple in one order)                                                                                |

## Key Differences and Limitations

### Subscription API Limitations

**Amendment Processing Order:**
The Subscription API processes amendments in a fixed type-based order:
1. Terms and conditions changes (if present)
2. Add operations
3. Update operations  
4. Remove operations
5. Change operations

Customers **cannot control** the sequence - the API automatically sorts amendments by type.

**Amendment Count Limits:**
- Default: Maximum 10 total amendments
- Add + Update + Remove + Change cannot exceed 9 (1 reserved for terms)
- Configurable via tenant settings
- An error is returned if limit exceeded

**Versioning:**
- Each amendment creates one new subscription version
- Multiple amendments in one call create multiple versions (e.g., 3 amendments = 3 new versions)

### Order API Advantages

**Simplified Versioning:**
All order actions in a single order create only ONE new subscription version, regardless of how many actions are included. This is much simpler than the Subscription API where each amendment creates a separate version.

**Flexible Action Sequencing:**
Order API allows you to specify the exact sequence of actions via the `orderActions[]` array order. This gives you complete control over how changes are applied.

**Multiple Action Types:**
You can mix and match different action types (AddProduct, UpdateProduct, RemoveProduct, ChangePlan, TermsAndConditions) in any order.

**Higher Action Limits:**
The Order API supports more actions per request:
- **Synchronous orders**: Up to 50 order actions
- **Asynchronous orders**: Up to 300 order actions

This is significantly more than the Subscription API's default limit of 9 amendments.

**Clearer Intent:**
Each order action explicitly declares its type, making the intent clearer and easier to understand.

## Amendment Type Mappings

### 1. Add Product Rate Plans

**Maps to:** `AddProduct` order action

Adds new product rate plans to an existing subscription.

#### Subscription API - Add

```json
PUT /v1/subscriptions/A-S00000123
{
  "add": [
    {
      "productRatePlanId": "2c92a0fe5a7d1234",
      "contractEffectiveDate": "2026-04-01",
      "chargeOverrides": [
        {
          "productRatePlanChargeId": "2c92a0fe5a7d5678",
          "pricing": {
            "recurringFlatFee": {
              "listPrice": 50.00
            }
          }
        }
      ]
    }
  ]
}
```

#### Order API - AddProduct

```json
POST /v1/orders
{
  "orderDate": "2026-04-01",
  "existingAccountNumber": "A00000001",
  "subscriptions": [
    {
      "subscriptionNumber": "A-S00000123",
      "orderActions": [
        {
          "type": "AddProduct",
          "addProduct": {
            "productRatePlanId": "2c92a0fe5a7d1234",
            "chargeOverrides": [
              {
                "productRatePlanChargeId": "2c92a0fe5a7d5678",
                "pricing": {
                  "recurringFlatFee": {
                    "listPrice": 50.00
                  }
                }
              }
            ]
          },
          "triggerDates": [
            {
              "name": "ContractEffective",
              "triggerDate": "2026-04-01"
            }
          ]
        }
      ]
    }
  ]
}
```

#### Add Field Mapping

| Subscription API Field | Order API Equivalent | Notes |
|------------------------|----------------------|-------|
| `add[]` | `orderActions[].addProduct` | Array of products to add |
| `add[].productRatePlanId` | `addProduct.productRatePlanId` | Product rate plan identifier |
| `add[].productRatePlanNumber` | `addProduct.productRatePlanNumber` | Alternative identifier |
| `add[].externallyManagedPlanId` | `addProduct.externallyManagedPlanId` | External plan ID |
| `add[].externalCatalogPlanId` | `addProduct.externalCatalogPlanId` | External catalog plan ID |
| `add[].contractEffectiveDate` | `triggerDates[name=ContractEffective].triggerDate` | Effective date |
| `add[].serviceActivationDate` | `triggerDates[name=ServiceActivation].triggerDate` | Service activation date |
| `add[].customerAcceptanceDate` | `triggerDates[name=CustomerAcceptance].triggerDate` | Customer acceptance date |
| `add[].chargeOverrides[]` | `addProduct.chargeOverrides[]` | Charge pricing overrides |
| `add[].customFieldsData` | `addProduct.ratePlanData` | Custom fields for rate plan |

### 2. Update Product Charges

**Maps to:** `UpdateProduct` order action

Updates pricing or quantity for existing product charges.

#### Subscription API - Update

```json
PUT /v1/subscriptions/A-S00000123
{
  "update": [
    {
      "ratePlanId": "2c92a0fd5b1a2345",
      "contractEffectiveDate": "2026-04-01",
      "chargeUpdateDetails": [
        {
          "ratePlanChargeId": "2c92a0fd5b1a3456",
          "pricing": {
            "recurringPerUnit": {
              "listPrice": 15.00,
              "quantity": 20
            }
          }
        }
      ]
    }
  ]
}
```

#### Order API - UpdateProduct

```json
POST /v1/orders
{
  "orderDate": "2026-04-01",
  "existingAccountNumber": "A00000001",
  "subscriptions": [
    {
      "subscriptionNumber": "A-S00000123",
      "orderActions": [
        {
          "type": "UpdateProduct",
          "updateProduct": {
            "ratePlanId": "2c92a0fd5b1a2345",
            "chargeUpdates": [
              {
                "chargeId": "2c92a0fd5b1a3456",
                "pricing": {
                  "recurringPerUnit": {
                    "listPrice": 15.00,
                    "quantity": 20
                  }
                }
              }
            ]
          },
          "triggerDates": [
            {
              "name": "ContractEffective",
              "triggerDate": "2026-04-01"
            }
          ]
        }
      ]
    }
  ]
}
```

#### Update Field Mapping

| Subscription API Field | Order API Equivalent | Notes |
|------------------------|----------------------|-------|
| `update[]` | `orderActions[].updateProduct` | Array of products to update |
| `update[].ratePlanId` | `updateProduct.ratePlanId` | Subscription rate plan ID to update |
| `update[].subscriptionRatePlanNumber` | `updateProduct.subscriptionRatePlanNumber` | Alternative identifier |
| `update[].contractEffectiveDate` | `triggerDates[name=ContractEffective].triggerDate` | Effective date |
| `update[].specificUpdateDate` | `triggerDates[name=SpecificUpdate].triggerDate` | Specific update date |
| `update[].chargeUpdateDetails[]` | `updateProduct.chargeUpdates[]` | Array of charge updates |
| `update[].chargeUpdateDetails[].ratePlanChargeId` | `chargeUpdates[].chargeId` | Charge ID to update |
| `update[].chargeUpdateDetails[].pricing` | `chargeUpdates[].pricing` | New pricing structure |
| `update[].customFieldsData` | `updateProduct.ratePlanData` | Custom fields for rate plan |

### 3. Remove Product Rate Plans

**Maps to:** `RemoveProduct` order action

Removes existing product rate plans from a subscription.

#### Subscription API - Remove

```json
PUT /v1/subscriptions/A-S00000123
{
  "remove": [
    {
      "ratePlanId": "2c92a0fd5b1a2345",
      "contractEffectiveDate": "2026-04-01"
    }
  ]
}
```

#### Order API - RemoveProduct

```json
POST /v1/orders
{
  "orderDate": "2026-04-01",
  "existingAccountNumber": "A00000001",
  "subscriptions": [
    {
      "subscriptionNumber": "A-S00000123",
      "orderActions": [
        {
          "type": "RemoveProduct",
          "removeProduct": {
            "ratePlanId": "2c92a0fd5b1a2345"
          },
          "triggerDates": [
            {
              "name": "ContractEffective",
              "triggerDate": "2026-04-01"
            }
          ]
        }
      ]
    }
  ]
}
```

#### Remove Field Mapping

| Subscription API Field | Order API Equivalent | Notes |
|------------------------|----------------------|-------|
| `remove[]` | `orderActions[].removeProduct` | Array of products to remove |
| `remove[].ratePlanId` | `removeProduct.ratePlanId` | Subscription rate plan ID to remove |
| `remove[].subscriptionRatePlanNumber` | `removeProduct.subscriptionRatePlanNumber` | Alternative identifier |
| `remove[].contractEffectiveDate` | `triggerDates[name=ContractEffective].triggerDate` | Effective date |
| `remove[].serviceActivationDate` | `triggerDates[name=ServiceActivation].triggerDate` | Service activation date |
| `remove[].customerAcceptanceDate` | `triggerDates[name=CustomerAcceptance].triggerDate` | Customer acceptance date |

### 4. Change Product Rate Plans (Upgrade/Downgrade)

**Maps to:** `ChangePlan` order action

Replaces an existing product rate plan with a different one (upgrade/downgrade scenario).

#### Subscription API - Change

```json
PUT /v1/subscriptions/A-S00000123
{
  "change": [
    {
      "ratePlanId": "2c92a0fd5b1a2345",
      "newProductRatePlanId": "2c92a0fe5a7d9999",
      "contractEffectiveDate": "2026-04-01",
      "effectivePolicy": "SpecificDate",
      "chargeOverrides": [
        {
          "productRatePlanChargeId": "2c92a0fe5a7d8888",
          "pricing": {
            "recurringFlatFee": {
              "listPrice": 100.00
            }
          }
        }
      ]
    }
  ]
}
```

#### Order API - ChangePlan

```json
POST /v1/orders
{
  "orderDate": "2026-04-01",
  "existingAccountNumber": "A00000001",
  "subscriptions": [
    {
      "subscriptionNumber": "A-S00000123",
      "orderActions": [
        {
          "type": "ChangePlan",
          "changePlan": {
            "oldRatePlanId": "2c92a0fd5b1a2345",
            "newProductRatePlanId": "2c92a0fe5a7d9999",
            "effectivePolicy": "SpecificDate",
            "chargeOverrides": [
              {
                "productRatePlanChargeId": "2c92a0fe5a7d8888",
                "pricing": {
                  "recurringFlatFee": {
                    "listPrice": 100.00
                  }
                }
              }
            ]
          },
          "triggerDates": [
            {
              "name": "ContractEffective",
              "triggerDate": "2026-04-01"
            }
          ]
        }
      ]
    }
  ]
}
```

#### Change Field Mapping

| Subscription API Field | Order API Equivalent | Notes |
|------------------------|----------------------|-------|
| `change[]` | `orderActions[].changePlan` | Array of plan changes |
| `change[].ratePlanId` | `changePlan.oldRatePlanId` | Current subscription rate plan ID |
| `change[].subscriptionRatePlanNumber` | `changePlan.oldSubscriptionRatePlanNumber` | Alternative identifier |
| `change[].newProductRatePlanId` | `changePlan.newProductRatePlanId` | New product rate plan ID |
| `change[].newProductRatePlanNumber` | `changePlan.newProductRatePlanNumber` | Alternative identifier |
| `change[].contractEffectiveDate` | `triggerDates[name=ContractEffective].triggerDate` | Effective date |
| `change[].effectivePolicy` | `changePlan.effectivePolicy` | When change takes effect |
| `change[].subType` | `changePlan.subType` | Change sub-type (e.g., Upgrade, Downgrade) |
| `change[].chargeOverrides[]` | `changePlan.chargeOverrides[]` | Charge pricing overrides for new plan |
| `change[].customFieldsData` | `changePlan.ratePlanData` | Custom fields for new rate plan |

### 5. Terms and Conditions Changes

**Maps to:** `TermsAndConditions` order action

Updates subscription term settings like renewal behavior, term length, and auto-renewal.

#### Subscription API - Terms Change

```json
PUT /v1/subscriptions/A-S00000123
{
  "termType": "TERMED",
  "currentTerm": 24,
  "currentTermPeriodType": "Month",
  "autoRenew": true,
  "renewalSetting": "RENEW_WITH_SPECIFIC_TERM",
  "renewalTerm": 12,
  "renewalTermPeriodType": "Month",
  "termStartDate": "2026-04-01",
  "termChangeContractEffectiveDate": "2026-04-01"
}
```

#### Order API - TermsAndConditions

```json
POST /v1/orders
{
  "orderDate": "2026-04-01",
  "existingAccountNumber": "A00000001",
  "subscriptions": [
    {
      "subscriptionNumber": "A-S00000123",
      "orderActions": [
        {
          "type": "TermsAndConditions",
          "termsAndConditions": {
            "initialTerm": {
              "termType": "TERMED",
              "startDate": "2026-04-01",
              "period": 24,
              "periodType": "Month"
            },
            "autoRenew": true,
            "renewalSetting": "RENEW_WITH_SPECIFIC_TERM",
            "renewalTerm": 12,
            "renewalTermPeriodType": "Month"
          },
          "triggerDates": [
            {
              "name": "ContractEffective",
              "triggerDate": "2026-04-01"
            }
          ]
        }
      ]
    }
  ]
}
```

#### Terms Field Mapping

| Subscription API Field | Order API Equivalent | Notes |
|------------------------|----------------------|-------|
| `termType` | `termsAndConditions.initialTerm.termType` | TERMED or EVERGREEN |
| `currentTerm` | `termsAndConditions.initialTerm.period` | Length of current term |
| `currentTermPeriodType` | `termsAndConditions.initialTerm.periodType` | Month, Year, Week, Day |
| `termStartDate` | `termsAndConditions.initialTerm.startDate` | Term start date |
| `autoRenew` | `termsAndConditions.autoRenew` | Auto-renewal enabled |
| `renewalSetting` | `termsAndConditions.renewalSetting` | Renewal behavior |
| `renewalTerm` | `termsAndConditions.renewalTerm` | Renewal term length |
| `renewalTermPeriodType` | `termsAndConditions.renewalTermPeriodType` | Renewal period type |
| `termChangeContractEffectiveDate` | `triggerDates[name=ContractEffective].triggerDate` | When term change takes effect |

### 6. Custom Fields Only Update

**Special Case:** Update subscription custom fields without any amendments.

#### Subscription API - Custom Fields Only

```json
PUT /v1/subscriptions/A-S00000123
{
  "customFieldsData": {
    "Custom_Field_1__c": "New Value",
    "Custom_Field_2__c": true
  }
}
```

#### Order API - Custom Fields Update

For custom fields only, you can use the Order API's update subscription action:

```json
POST /v1/orders
{
  "orderDate": "2026-04-01",
  "existingAccountNumber": "A00000001",
  "subscriptions": [
    {
      "subscriptionNumber": "A-S00000123",
      "subscriptionData": {
        "Custom_Field_1__c": "New Value",
        "Custom_Field_2__c": true
      }
    }
  ],
  "processingOptions": {
    "updateSubscriptionOnly": true
  }
}
```

**Note:** When only updating custom fields with no order actions, the Subscription API updates the subscription in place without creating a new version.

## Complete Examples

### Example 1: Multiple Amendments in One Call

A common scenario: Add a new product, update an existing charge, and change terms.

**Subscription API:**
```json
PUT /v1/subscriptions/A-S00000123
{
  "add": [
    {
      "productRatePlanId": "2c92a0fe5a7d1234",
      "contractEffectiveDate": "2026-04-01"
    }
  ],
  "update": [
    {
      "ratePlanId": "2c92a0fd5b1a2345",
      "contractEffectiveDate": "2026-04-01",
      "chargeUpdateDetails": [
        {
          "ratePlanChargeId": "2c92a0fd5b1a3456",
          "pricing": {
            "recurringPerUnit": {
              "listPrice": 25.00,
              "quantity": 10
            }
          }
        }
      ]
    }
  ],
  "autoRenew": true,
  "renewalSetting": "RENEW_WITH_SPECIFIC_TERM",
  "renewalTerm": 12,
  "renewalTermPeriodType": "Month"
}
```

**Important:** The Subscription API processes these in this order:
1. Terms change (auto-renew settings) - creates version 2
2. Add operation - creates version 3
3. Update operation - creates version 4

**Total: 3 new subscription versions created** (assuming original subscription was version 1).

**Order API:**
```json
POST /v1/orders
{
  "orderDate": "2026-04-01",
  "existingAccountNumber": "A00000001",
  "subscriptions": [
    {
      "subscriptionNumber": "A-S00000123",
      "orderActions": [
        {
          "type": "TermsAndConditions",
          "termsAndConditions": {
            "autoRenew": true,
            "renewalSetting": "RENEW_WITH_SPECIFIC_TERM",
            "renewalTerm": 12,
            "renewalTermPeriodType": "Month"
          },
          "triggerDates": [
            {
              "name": "ContractEffective",
              "triggerDate": "2026-04-01"
            }
          ]
        },
        {
          "type": "AddProduct",
          "addProduct": {
            "productRatePlanId": "2c92a0fe5a7d1234"
          },
          "triggerDates": [
            {
              "name": "ContractEffective",
              "triggerDate": "2026-04-01"
            }
          ]
        },
        {
          "type": "UpdateProduct",
          "updateProduct": {
            "ratePlanId": "2c92a0fd5b1a2345",
            "chargeUpdates": [
              {
                "chargeId": "2c92a0fd5b1a3456",
                "pricing": {
                  "recurringPerUnit": {
                    "listPrice": 25.00,
                    "quantity": 10
                  }
                }
              }
            ]
          },
          "triggerDates": [
            {
              "name": "ContractEffective",
              "triggerDate": "2026-04-01"
            }
          ]
        }
      ]
    }
  ]
}
```

**Key Difference - Versioning:**
- **Subscription API**: Creates 3 new versions (one per amendment)
- **Order API**: Creates only 1 new version (all actions in one order)

**Note:** You can reorder these actions in the Order API to control the sequence!

### Example 2: Upgrade with Custom Sequence

Upgrade a plan and add another product, but add the product first (not possible in Subscription API).

**Order API:**
```json
POST /v1/orders
{
  "orderDate": "2026-04-01",
  "existingAccountNumber": "A00000001",
  "subscriptions": [
    {
      "subscriptionNumber": "A-S00000123",
      "orderActions": [
        {
          "type": "AddProduct",
          "addProduct": {
            "productRatePlanId": "2c92a0fe5a7d9876"
          },
          "triggerDates": [
            {
              "name": "ContractEffective",
              "triggerDate": "2026-04-01"
            }
          ]
        },
        {
          "type": "ChangePlan",
          "changePlan": {
            "oldRatePlanId": "2c92a0fd5b1a2345",
            "newProductRatePlanId": "2c92a0fe5a7d9999",
            "effectivePolicy": "SpecificDate"
          },
          "triggerDates": [
            {
              "name": "ContractEffective",
              "triggerDate": "2026-04-01"
            }
          ]
        }
      ]
    }
  ]
}
```

**Key Difference:** In the Subscription API, the `change` operation would always execute AFTER the `add` operation regardless of how you order them in the request. In the Order API, you have complete control.

### Example 3: Maximum Amendments (9 actions)

Testing the limit with multiple operations.

**Subscription API:**
```json
PUT /v1/subscriptions/A-S00000123
{
  "add": [
    { "productRatePlanId": "2c92a0fe5a7d0001", "contractEffectiveDate": "2026-04-01" },
    { "productRatePlanId": "2c92a0fe5a7d0002", "contractEffectiveDate": "2026-04-01" },
    { "productRatePlanId": "2c92a0fe5a7d0003", "contractEffectiveDate": "2026-04-01" }
  ],
  "update": [
    { "ratePlanId": "2c92a0fd5b1a0001", "contractEffectiveDate": "2026-04-01", "chargeUpdateDetails": [...] },
    { "ratePlanId": "2c92a0fd5b1a0002", "contractEffectiveDate": "2026-04-01", "chargeUpdateDetails": [...] },
    { "ratePlanId": "2c92a0fd5b1a0003", "contractEffectiveDate": "2026-04-01", "chargeUpdateDetails": [...] }
  ],
  "remove": [
    { "ratePlanId": "2c92a0fd5b1a0004", "contractEffectiveDate": "2026-04-01" },
    { "ratePlanId": "2c92a0fd5b1a0005", "contractEffectiveDate": "2026-04-01" },
    { "ratePlanId": "2c92a0fd5b1a0006", "contractEffectiveDate": "2026-04-01" }
  ]
}
```

**Total:** 9 amendments (3 add + 3 update + 3 remove) - This is at the default limit.

**Order API equivalent:**
```json
POST /v1/orders
{
  "orderDate": "2026-04-01",
  "existingAccountNumber": "A00000001",
  "subscriptions": [
    {
      "subscriptionNumber": "A-S00000123",
      "orderActions": [
        { "type": "AddProduct", "addProduct": { "productRatePlanId": "2c92a0fe5a7d0001" }, ... },
        { "type": "AddProduct", "addProduct": { "productRatePlanId": "2c92a0fe5a7d0002" }, ... },
        { "type": "AddProduct", "addProduct": { "productRatePlanId": "2c92a0fe5a7d0003" }, ... },
        { "type": "UpdateProduct", "updateProduct": { "ratePlanId": "2c92a0fd5b1a0001", ... }, ... },
        { "type": "UpdateProduct", "updateProduct": { "ratePlanId": "2c92a0fd5b1a0002", ... }, ... },
        { "type": "UpdateProduct", "updateProduct": { "ratePlanId": "2c92a0fd5b1a0003", ... }, ... },
        { "type": "RemoveProduct", "removeProduct": { "ratePlanId": "2c92a0fd5b1a0004" }, ... },
        { "type": "RemoveProduct", "removeProduct": { "ratePlanId": "2c92a0fd5b1a0005" }, ... },
        { "type": "RemoveProduct", "removeProduct": { "ratePlanId": "2c92a0fd5b1a0006" }, ... }
      ]
    }
  ]
}
```

**Order API:** Can handle significantly more actions (up to 50 for synchronous calls, 300 for asynchronous calls).

## Code Examples

### Python - Add and Update

**Before (Subscription API):**
```python
import requests

url = f"https://rest.zuora.com/v1/subscriptions/{subscription_key}"

payload = {
    "add": [
        {
            "productRatePlanId": "2c92a0fe5a7d1234",
            "contractEffectiveDate": "2026-04-01"
        }
    ],
    "update": [
        {
            "ratePlanId": "2c92a0fd5b1a2345",
            "contractEffectiveDate": "2026-04-01",
            "chargeUpdateDetails": [
                {
                    "ratePlanChargeId": "2c92a0fd5b1a3456",
                    "pricing": {
                        "recurringPerUnit": {
                            "listPrice": 25.00,
                            "quantity": 10
                        }
                    }
                }
            ]
        }
    ]
}

response = requests.put(url, json=payload, headers=headers)
```

**After (Order API):**
```python
import requests

url = "https://rest.zuora.com/v1/orders"

payload = {
    "orderDate": "2026-04-01",
    "existingAccountNumber": "A00000001",
    "subscriptions": [
        {
            "subscriptionNumber": subscription_number,
            "orderActions": [
                {
                    "type": "AddProduct",
                    "addProduct": {
                        "productRatePlanId": "2c92a0fe5a7d1234"
                    },
                    "triggerDates": [
                        {
                            "name": "ContractEffective",
                            "triggerDate": "2026-04-01"
                        }
                    ]
                },
                {
                    "type": "UpdateProduct",
                    "updateProduct": {
                        "ratePlanId": "2c92a0fd5b1a2345",
                        "chargeUpdates": [
                            {
                                "chargeId": "2c92a0fd5b1a3456",
                                "pricing": {
                                    "recurringPerUnit": {
                                        "listPrice": 25.00,
                                        "quantity": 10
                                    }
                                }
                            }
                        ]
                    },
                    "triggerDates": [
                        {
                            "name": "ContractEffective",
                            "triggerDate": "2026-04-01"
                        }
                    ]
                }
            ]
        }
    ]
}

response = requests.post(url, json=payload, headers=headers)
```

### JavaScript - Change Plan

**Before (Subscription API):**
```javascript
const url = `https://rest.zuora.com/v1/subscriptions/${subscriptionKey}`;

const payload = {
  change: [
    {
      ratePlanId: '2c92a0fd5b1a2345',
      newProductRatePlanId: '2c92a0fe5a7d9999',
      contractEffectiveDate: '2026-04-01',
      effectivePolicy: 'SpecificDate'
    }
  ]
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
  orderDate: '2026-04-01',
  existingAccountNumber: 'A00000001',
  subscriptions: [
    {
      subscriptionNumber: subscriptionNumber,
      orderActions: [
        {
          type: 'ChangePlan',
          changePlan: {
            oldRatePlanId: '2c92a0fd5b1a2345',
            newProductRatePlanId: '2c92a0fe5a7d9999',
            effectivePolicy: 'SpecificDate'
          },
          triggerDates: [
            {
              name: 'ContractEffective',
              triggerDate: '2026-04-01'
            }
          ]
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

### Java - Terms and Conditions

**Before (Subscription API):**
```java
String url = "https://rest.zuora.com/v1/subscriptions/" + subscriptionKey;

JSONObject payload = new JSONObject();
payload.put("autoRenew", true);
payload.put("renewalSetting", "RENEW_WITH_SPECIFIC_TERM");
payload.put("renewalTerm", 12);
payload.put("renewalTermPeriodType", "Month");

HttpPut request = new HttpPut(url);
request.setEntity(new StringEntity(payload.toString()));
HttpResponse response = httpClient.execute(request);
```

**After (Order API):**
```java
String url = "https://rest.zuora.com/v1/orders";

JSONObject payload = new JSONObject();
payload.put("orderDate", "2026-04-01");
payload.put("existingAccountNumber", "A00000001");

JSONArray subscriptions = new JSONArray();
JSONObject subscription = new JSONObject();
subscription.put("subscriptionNumber", subscriptionNumber);

JSONArray orderActions = new JSONArray();
JSONObject orderAction = new JSONObject();
orderAction.put("type", "TermsAndConditions");

JSONObject termsAndConditions = new JSONObject();
termsAndConditions.put("autoRenew", true);
termsAndConditions.put("renewalSetting", "RENEW_WITH_SPECIFIC_TERM");
termsAndConditions.put("renewalTerm", 12);
termsAndConditions.put("renewalTermPeriodType", "Month");

orderAction.put("termsAndConditions", termsAndConditions);

JSONArray triggerDates = new JSONArray();
JSONObject triggerDate = new JSONObject();
triggerDate.put("name", "ContractEffective");
triggerDate.put("triggerDate", "2026-04-01");
triggerDates.put(triggerDate);

orderAction.put("triggerDates", triggerDates);
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
  "totalDeltaMrr": 150.00,
  "totalDeltaTcv": 1800.00,
  "orderNumbers": ["O-00001234", "O-00001235", "O-00001236"],
  "invoiceId": "2c92a0fe...",
  "creditMemoId": null
}
```

**Key Fields:**
- `subscriptionId`: The latest subscription version ID
- `totalDeltaMrr`: Change in monthly recurring revenue
- `totalDeltaTcv`: Change in total contract value
- `orderNumbers`: Order numbers if Order feature is enabled (coexistence mode)

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
      "orderActions": [
        {
          "type": "AddProduct",
          "sequence": 0,
          "status": "Completed"
        },
        {
          "type": "UpdateProduct",
          "sequence": 1,
          "status": "Completed"
        }
      ]
    }
  ]
}
```

**Key Differences:**
- Order API returns `orderNumber` for tracking
- `orderActions[]` shows status of each action
- `sequence` indicates the order in which actions were processed

## Migration Checklist

- [ ] Identify all subscription update API calls in your code
- [ ] Determine which amendment types are used: add, update, remove, change, terms
- [ ] Map `add[]` operations to `AddProduct` order actions
- [ ] Map `update[]` operations to `UpdateProduct` order actions
- [ ] Map `remove[]` operations to `RemoveProduct` order actions
- [ ] Map `change[]` operations to `ChangePlan` order actions
- [ ] Map root-level term fields to `TermsAndConditions` order action
- [ ] Update endpoint from `PUT /v1/subscriptions/{key}` to `POST /v1/orders`
- [ ] Wrap each amendment in an `orderActions[]` entry with explicit type
- [ ] Convert effective dates to `triggerDates[]` array structure
- [ ] Decide on action sequence (now customer-controlled!)
- [ ] Update response handling for new structure
- [ ] Test amendment count limits (Order API: 50 sync/300 async vs Subscription API: 9)
- [ ] Test custom fields only updates
- [ ] Verify action sequencing behavior
- [ ] Test in sandbox environment with all amendment combinations

## Important Notes

### Action Sequence Control

**Subscription API:** Fixed sequence based on amendment type (cannot be changed):
1. Terms and conditions
2. Add
3. Update
4. Remove
5. Change

**Order API:** You control the sequence via the order of items in the `orderActions[]` array.

### Amendment Count Limits

**Subscription API:**
- Default maximum: 9 amendments (add + update + remove + change)
- Terms changes count separately (10 total including terms)
- Configurable but requires tenant property change
- An error is returned if the limit is exceeded

**Order API:**
- **Synchronous orders**: Maximum 50 order actions per request
- **Asynchronous orders**: Maximum 300 order actions per request
- Significantly higher limits than the Subscription API
- Better suited for complex scenarios with many changes

### Versioning Behavior

**Key Difference:**
- **Subscription API:** Each amendment creates a new subscription version. If you have 3 amendments (add, update, remove), you get 3 new versions.
- **Order API:** All order actions in a single order create only ONE new subscription version, regardless of how many actions you include. This is a major simplification.

### Custom Fields Only

When updating only custom fields (no amendments):
- **Subscription API:** Updates in place, no new version created
- **Order API:** Use `subscriptionData` with `updateSubscriptionOnly` flag

### Preview Mode

Both APIs support preview mode:
- **Subscription API:** `"preview": true` in request body
- **Order API:** Use preview endpoint or processing options

## Error Handling

### Common Errors

**Error: Too many amendments**
```json
{
  "success": false,
  "reasons": [{
    "message": "The number of amendments exceeds the limit"
  }]
}
```
**Solution:** Reduce the number of amendments or split into multiple calls. With Order API, you have more flexibility.

**Error: Invalid rate plan ID**
```json
{
  "success": false,
  "reasons": [{
    "code": 53100040,
    "message": "Invalid rate plan ID"
  }]
}
```
**Solution:** Verify the rate plan ID exists and belongs to the subscription.

**Error: Invalid effective date**
```json
{
  "success": false,
  "reasons": [{
    "code": 53100040,
    "message": "Contract effective date cannot be in the past"
  }]
}
```
**Solution:** Ensure all effective dates are valid for the subscription.

## Resources

- [Order API Documentation](https://www.zuora.com/developer/api-references/api/tag/Orders)
- [Subscription Update API Documentation](https://www.zuora.com/developer/api-references/api/operation/PUT_Subscription/)
- [Amendment Types Guide](https://knowledgecenter.zuora.com/)
- [Order API Best Practices](https://www.zuora.com/developer/)
