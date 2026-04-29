# Subscribe Action API to Order API Migration Guide

## Overview

This document provides field-accurate mappings for migrating from Zuora's Subscribe Action API (`POST /v1/action/subscribe`) to the Order API (`POST /v1/orders` with `CreateSubscription` action).

The Subscribe API is a "one-stop" API that creates accounts, contacts, payment methods, and subscriptions in a single call. The Order API provides equivalent functionality with more flexibility and modern capabilities.

## API Comparison

| Aspect | Subscribe Action API | Order API (Create) | Order API (Preview) |
|--------|---------------------|-------------------|---------------------|
| Endpoint | `POST /v1/action/subscribe` | `POST /v1/orders` | `POST /v1/orders/preview` |
| Mode Control | `PreviewOptions` parameter | N/A (always creates) | `previewOptions` required |
| Primary Use | Create or preview account + subscription | Create account + subscription | Preview billing/metrics without creating |
| Account Creation | Embedded in request (`Account` object) | `newAccount` or `existingAccountNumber` | `previewAccountInfo` or `existingAccountNumber` |
| Action Type | Implicit (subscribe) | Explicit (`CreateSubscription`) | Explicit (`CreateSubscription`) |
| Billing Control | `SubscribeOptions.generateInvoice` | `processingOptions.runBilling` | N/A (preview only) |
| Payment Control | `SubscribeOptions.processPayments` | `processingOptions.collect` | N/A (preview only) |
| Future Dating | Limited | Native support with `orderDate` | Native support with `orderDate` |
| Atomic Operations | Single subscription only | Multiple actions per order | Multiple actions per order |

## Subscribe API Modes

The Subscribe Action API supports two modes determined by the `PreviewOptions` parameter:

### Mode 1: Create (Actual Subscription Creation)
When `PreviewOptions` is **NOT** provided or is empty, the API creates the actual subscription.

**Migration Path:** → `POST /v1/orders` (Order Create API)

### Mode 2: Preview (No Actual Creation)
When `PreviewOptions` is provided with preview settings, the API returns preview results without creating the subscription.

**Migration Path:** → `POST /v1/orders/preview` (Order Preview API)

## Migration Scenarios

### Scenario 1: New Account + Subscription

When the Subscribe API creates a new account along with the subscription.

**Subscribe API Request:**
```json
POST /v1/action/subscribe
{
  "Account": {
    "name": "Example Corp",
    "currency": "USD",
    "billCycleDay": 1,
    "autoPay": true,
    "batch": "Batch1",
    "billToContact": {
      "firstName": "John",
      "lastName": "Doe",
      "address1": "123 Main St",
      "city": "San Francisco",
      "state": "CA",
      "postalCode": "94105",
      "country": "USA",
      "workEmail": "john.doe@example.com"
    },
    "paymentMethod": {
      "type": "CreditCard",
      "creditCardNumber": "4111111111111111",
      "creditCardType": "Visa",
      "expirationMonth": 12,
      "expirationYear": 2025,
      "securityCode": "123"
    }
  },
  "SubscribeOptions": {
    "generateInvoice": true,
    "processPayments": true
  },
  "SubscriptionData": {
    "Subscription": {
      "termType": "TERMED",
      "contractEffectiveDate": "2026-04-20",
      "serviceActivationDate": "2026-04-20",
      "customerAcceptanceDate": "2026-04-20",
      "initialTerm": 12,
      "renewalTerm": 12,
      "autoRenew": true
    },
    "RatePlanData": [{
      "RatePlan": {
        "productRatePlanId": "2c92a0fd8c7f6e5b018c7f9a12345678"
      },
      "RatePlanChargeData": [{
        "RatePlanCharge": {
          "quantity": 5
        }
      }]
    }]
  }
}
```

**Order API Equivalent:**
```json
POST /v1/orders
{
  "orderDate": "2026-04-20",
  "processingOptions": {
    "runBilling": true,
    "collect": true
  },
  "newAccount": {
    "accountNumber": "A00000123",
    "name": "Example Corp",
    "currency": "USD",
    "billCycleDay": 1,
    "autoPay": true,
    "batch": "Batch1",
    "billToContact": {
      "firstName": "John",
      "lastName": "Doe",
      "address1": "123 Main St",
      "city": "San Francisco",
      "state": "CA",
      "postalCode": "94105",
      "country": "USA",
      "workEmail": "john.doe@example.com"
    },
    "paymentMethod": {
      "type": "CreditCard",
      "cardNumber": "4111111111111111",
      "cardType": "Visa",
      "expirationMonth": 12,
      "expirationYear": 2025,
      "securityCode": "123"
    }
  },
  "subscriptions": [{
    "orderActions": [{
      "type": "CreateSubscription",
      "triggerDates": [{
        "name": "ContractEffective",
        "triggerDate": "2026-04-20"
      }, {
        "name": "ServiceActivation",
        "triggerDate": "2026-04-20"
      }, {
        "name": "CustomerAcceptance",
        "triggerDate": "2026-04-20"
      }],
      "createSubscription": {
        "terms": {
          "initialTerm": {
            "period": 12,
            "periodType": "Month",
            "termType": "TERMED"
          },
          "autoRenew": true,
          "renewalSetting": "RENEW_WITH_SPECIFIC_TERM",
          "renewalTerms": [{
            "period": 12,
            "periodType": "Month"
          }]
        },
        "subscribeToRatePlans": [{
          "productRatePlanId": "2c92a0fd8c7f6e5b018c7f9a12345678",
          "chargeOverrides": [{
            "pricing": {
              "recurringPerUnit": {
                "quantity": 5
              }
            }
          }]
        }]
      }
    }]
  }]
}
```

### Scenario 2: Existing Account + Subscription

When the Subscribe API uses an existing account (by passing `accountKey` in Account object).

**Subscribe API Request:**
```json
POST /v1/action/subscribe
{
  "Account": {
    "accountKey": "A00000001"
  },
  "SubscribeOptions": {
    "generateInvoice": true,
    "processPayments": false
  },
  "SubscriptionData": {
    "Subscription": {
      "termType": "EVERGREEN",
      "contractEffectiveDate": "2026-04-20"
    },
    "RatePlanData": [{
      "RatePlan": {
        "productRatePlanId": "2c92a0fd8c7f6e5b018c7f9a12345678"
      }
    }]
  }
}
```

**Order API Equivalent:**
```json
POST /v1/orders
{
  "orderDate": "2026-04-20",
  "existingAccountNumber": "A00000001",
  "processingOptions": {
    "runBilling": true,
    "collect": false
  },
  "subscriptions": [{
    "orderActions": [{
      "type": "CreateSubscription",
      "triggerDates": [{
        "name": "ContractEffective",
        "triggerDate": "2026-04-20"
      }],
      "createSubscription": {
        "terms": {
          "initialTerm": {
            "termType": "EVERGREEN"
          },
          "autoRenew": false
        },
        "subscribeToRatePlans": [{
          "productRatePlanId": "2c92a0fd8c7f6e5b018c7f9a12345678"
        }]
      }
    }]
  }]
}
```

### Scenario 3: Preview Mode (No Actual Creation)

When the Subscribe API is called with `PreviewOptions`, it returns preview results without creating the subscription. This maps to the Order Preview API.

**Subscribe API Request (with PreviewOptions):**
```json
POST /v1/action/subscribe
{
  "Account": {
    "name": "Example Corp",
    "currency": "USD",
    "billCycleDay": 1,
    "billToContact": {
      "firstName": "Jane",
      "lastName": "Smith",
      "address1": "456 Oak Ave",
      "city": "Boston",
      "state": "MA",
      "postalCode": "02101",
      "country": "USA",
      "workEmail": "jane@example.com"
    }
  },
  "SubscribeOptions": {
    "generateInvoice": true,
    "processPayments": false
  },
  "PreviewOptions": {
    "enablePreviewMode": true,
    "numberOfPeriods": 3
  },
  "SubscriptionData": {
    "Subscription": {
      "termType": "TERMED",
      "contractEffectiveDate": "2026-05-01",
      "initialTerm": 12,
      "autoRenew": true,
      "renewalTerm": 12
    },
    "RatePlanData": [{
      "RatePlan": {
        "productRatePlanId": "2c92a0fd8c7f6e5b018c7f9a12345678"
      }
    }]
  }
}
```

**Order Preview API Equivalent:**
```json
POST /v1/orders/preview
{
  "orderDate": "2026-05-01",
  "previewAccountInfo": {
    "name": "Example Corp",
    "currency": "USD",
    "billCycleDay": 1,
    "billToContact": {
      "firstName": "Jane",
      "lastName": "Smith",
      "address1": "456 Oak Ave",
      "city": "Boston",
      "state": "MA",
      "postalCode": "02101",
      "country": "USA",
      "workEmail": "jane@example.com"
    }
  },
  "previewOptions": {
    "previewTypes": ["BillingDocs", "ChargeMetrics"],
    "previewNumberOfPeriods": 3
  },
  "subscriptions": [{
    "orderActions": [{
      "type": "CreateSubscription",
      "triggerDates": [{
        "name": "ContractEffective",
        "triggerDate": "2026-05-01"
      }],
      "createSubscription": {
        "terms": {
          "initialTerm": {
            "period": 12,
            "periodType": "Month",
            "termType": "TERMED"
          },
          "autoRenew": true,
          "renewalSetting": "RENEW_WITH_SPECIFIC_TERM",
          "renewalTerms": [{
            "period": 12,
            "periodType": "Month"
          }]
        },
        "subscribeToRatePlans": [{
          "productRatePlanId": "2c92a0fd8c7f6e5b018c7f9a12345678"
        }]
      }
    }]
  }]
}
```

**Key Differences for Preview Mode:**

1. **Endpoint Changes**: `POST /v1/orders` → `POST /v1/orders/preview`
2. **Account Field**: `newAccount` → `previewAccountInfo` (for new accounts)
3. **Required Field**: `previewOptions` is **required** for preview API
4. **No Processing Options**: `processingOptions` is not used in preview mode (no actual billing/collection)
5. **Preview Types**: Must specify `previewTypes: ["BillingDocs", "ChargeMetrics"]` (Subscribe API only supports these two types)

## Field Mapping Tables

### Top-Level Request Fields

| Subscribe API Field | Order API Field | Notes |
|---------------------|-----------------|-------|
| `Account` | `newAccount`, `existingAccountNumber`, or `previewAccountInfo` | Use `newAccount` (create mode) or `previewAccountInfo` (preview mode) for new accounts; `existingAccountNumber` for existing |
| `SubscribeOptions` | `processingOptions` | Billing and payment options move to order level (only in create mode, not in preview) |
| `SubscriptionData` | `subscriptions[].orderActions[]` | Subscription becomes a `CreateSubscription` action |
| `PreviewOptions` | `previewOptions` + endpoint change | **If present**: triggers preview mode → use `/v1/orders/preview` endpoint and `previewOptions` field. **If absent**: use `/v1/orders` endpoint (create mode) |
| N/A | `orderDate` | **New required field** - typically same as `contractEffectiveDate` |

### Account Object Mapping

#### For New Accounts

| Subscribe API Field | Order API Field | Notes |
|---------------------|-----------------|-------|
| `Account.name` | `newAccount.name` | Same |
| `Account.accountNumber` | `newAccount.accountNumber` | Optional in both |
| `Account.currency` | `newAccount.currency` | Required in both |
| `Account.billCycleDay` | `newAccount.billCycleDay` | Same |
| `Account.autoPay` | `newAccount.autoPay` | Same |
| `Account.batch` | `newAccount.batch` | Same |
| `Account.billToContact` | `newAccount.billToContact` | See Contact mapping below |
| `Account.soldToContact` | `newAccount.soldToContact` | Optional, defaults to billToContact |
| `Account.paymentMethod` | `newAccount.paymentMethod` | See Payment Method mapping below |
| `Account.taxInfo` | `newAccount.taxInfo` | Same structure |
| `Account.customField__c` | `newAccount.customField__c` | Custom fields preserved |

#### For Existing Accounts

| Subscribe API Field | Order API Field | Notes |
|---------------------|-----------------|-------|
| `Account.accountKey` | `existingAccountNumber` | Account number or ID |
| `Account.paymentMethod` | Use existing or create via separate API | Order API doesn't create payment methods for existing accounts |

### Contact Object Mapping

| Subscribe API Field | Order API Field | Notes |
|---------------------|-----------------|-------|
| `billToContact.firstName` | `newAccount.billToContact.firstName` | Same |
| `billToContact.lastName` | `newAccount.billToContact.lastName` | Same |
| `billToContact.address1` | `newAccount.billToContact.address1` | Same |
| `billToContact.address2` | `newAccount.billToContact.address2` | Same |
| `billToContact.city` | `newAccount.billToContact.city` | Same |
| `billToContact.state` | `newAccount.billToContact.state` | Same |
| `billToContact.postalCode` | `newAccount.billToContact.postalCode` | Same |
| `billToContact.country` | `newAccount.billToContact.country` | Same |
| `billToContact.workEmail` | `newAccount.billToContact.workEmail` | Same |
| `billToContact.workPhone` | `newAccount.billToContact.workPhone` | Same |

Note: `soldToContact` follows the same mapping pattern.

### Payment Method Mapping

| Subscribe API Field | Order API Field | Notes |
|---------------------|-----------------|-------|
| `paymentMethod.type` | `newAccount.paymentMethod.type` | Same values: "CreditCard", "ACH", etc. |
| `paymentMethod.creditCardNumber` | `newAccount.paymentMethod.cardNumber` | **Field name changed** |
| `paymentMethod.creditCardType` | `newAccount.paymentMethod.cardType` | **Field name changed** |
| `paymentMethod.expirationMonth` | `newAccount.paymentMethod.expirationMonth` | Same |
| `paymentMethod.expirationYear` | `newAccount.paymentMethod.expirationYear` | Same |
| `paymentMethod.securityCode` | `newAccount.paymentMethod.securityCode` | Same |
| `paymentMethod.creditCardHolderName` | `newAccount.paymentMethod.cardHolderName` | **Field name changed** |

**Important:** For existing accounts, payment methods cannot be created via Order API. Use the Payment Methods API separately if needed.

### Subscribe Options Mapping

| Subscribe API Field | Order API Field | Notes |
|---------------------|-----------------|-------|
| `SubscribeOptions.generateInvoice` | `processingOptions.runBilling` | Generates invoice and invoice items. **Default: `false`** |
| `SubscribeOptions.processPayments` | `processingOptions.collect` | Processes payment if invoice generated. **Default: `false`** |
| `SubscribeOptions.applyCreditBalance` | `processingOptions.applyCreditBalance` | Apply account credit balance |
| `SubscribeOptions.electronicPaymentMethodId` | `electronicPaymentOptions.paymentMethodId` | Specify which payment method to use for electronic payment collection |

**Important Notes:**
- These mappings apply only to Create mode. In Preview mode, `processingOptions` is not used.
- **Default values**: Both `generateInvoice` and `processPayments` default to `false` in the Subscribe API implementation. If omitted, no invoice or payment processing occurs.
- When migrating to Order API, if the Subscribe API code omits these fields, you should also omit `processingOptions` or explicitly set `runBilling: false` and `collect: false`.

### Preview Options Mapping

| Subscribe API Field | Order API Field | Notes |
|---------------------|-----------------|-------|
| `PreviewOptions.enablePreviewMode` | Endpoint change | Presence triggers preview mode → use `/v1/orders/preview` |
| `PreviewOptions.numberOfPeriods` | `previewOptions.previewNumberOfPeriods` | Number of billing periods to preview |
| N/A | `previewOptions.previewTypes` | **Required** array: `["BillingDocs", "ChargeMetrics"]` for Subscribe API migration |
| N/A | `previewOptions.previewThruType` | Optional: "SpecificDate", "NumberOfPeriods" |
| N/A | `previewOptions.specificPreviewThruDate` | Optional: Specific end date for preview |
| N/A | `previewOptions.chargeTypeToExclude` | Optional: Array of charge types to exclude |
| N/A | `previewOptions.skipTax` | Optional: Skip tax calculation (default: false) |
| N/A | `previewOptions.validateScheduledOrders` | Optional: Validate scheduled orders (default: false) |

**Available Preview Types (Order API supports all, Subscribe API migration uses subset):**
- `BillingDocs` - Preview billing documents (invoices, credit memos) ✅ **Use for Subscribe API**
- `ChargeMetrics` - Preview charge-level metrics ✅ **Use for Subscribe API**
- `OrderMetrics` - Preview order-level metrics ❌ **Not available in Subscribe API preview**
- `RampMetrics` - Preview ramp metrics (for ramp deals) ❌ **Not available in Subscribe API preview**
- `RampDeltaMetrics` - Preview ramp delta metrics ❌ **Not available in Subscribe API preview**
- `OrderDeltaMetrics` - Preview order delta metrics ❌ **Not available in Subscribe API preview**

**Important Preview Mode Notes:**
1. `previewTypes` is **required** in Order Preview API (must specify at least one type)
2. **For Subscribe API migration**: Only use `["BillingDocs", "ChargeMetrics"]` - these match Subscribe API's preview capabilities
3. For new accounts, use `previewAccountInfo` instead of `newAccount`
4. For existing accounts, use `existingAccountNumber` as usual
5. `processingOptions` is not applicable in preview mode
5. Preview API returns projected billing data without creating actual records

### Subscription Object Mapping

| Subscribe API Field | Order API Field | Notes |
|---------------------|-----------------|-------|
| `Subscription.termType` | `createSubscription.terms.initialTerm.termType` | "TERMED" or "EVERGREEN" |
| `Subscription.contractEffectiveDate` | `triggerDates[name="ContractEffective"].triggerDate` | Also set as `orderDate` typically |
| `Subscription.serviceActivationDate` | `triggerDates[name="ServiceActivation"].triggerDate` | Optional trigger date |
| `Subscription.customerAcceptanceDate` | `triggerDates[name="CustomerAcceptance"].triggerDate` | Optional trigger date |
| `Subscription.initialTerm` | `createSubscription.terms.initialTerm.period` | Number of periods |
| `Subscription.initialTermPeriodType` | `createSubscription.terms.initialTerm.periodType` | "Month", "Year", etc. (defaults to Month) |
| `Subscription.renewalTerm` | `createSubscription.terms.renewalTerms[0].period` | Number of periods for renewal |
| `Subscription.renewalTermPeriodType` | `createSubscription.terms.renewalTerms[0].periodType` | "Month", "Year", etc. |
| `Subscription.autoRenew` | `createSubscription.terms.autoRenew` | Boolean |
| `Subscription.notes` | `createSubscription.notes` | Same |
| `Subscription.customField__c` | `createSubscription.customField__c` | Custom fields preserved |

**Important Term Mapping Notes:**

For **TERMED** subscriptions:
- Must specify `initialTerm.period` and `initialTerm.periodType`
- If `autoRenew` is true, must specify `renewalSetting` and `renewalTerms`

For **EVERGREEN** subscriptions:
- Set `initialTerm.termType` to "EVERGREEN"
- Set `autoRenew` to false
- No `renewalTerms` needed

### Rate Plan Data Mapping

| Subscribe API Field | Order API Field | Notes |
|---------------------|-----------------|-------|
| `RatePlanData[].RatePlan.productRatePlanId` | `subscribeToRatePlans[].productRatePlanId` | Same |
| `RatePlanData[].RatePlanChargeData[]` | `subscribeToRatePlans[].chargeOverrides[]` | Charge-level overrides |

### Rate Plan Charge Overrides

| Subscribe API Field | Order API Field | Notes |
|---------------------|-----------------|-------|
| `RatePlanCharge.quantity` | `chargeOverrides[].pricing.{chargeModel}.quantity` | **Charge model dependent:** `recurringPerUnit.quantity`, `recurringTiered.quantity`, etc. Not applicable for flat fee charges |
| `RatePlanCharge.price` | `chargeOverrides[].pricing.{chargeModel}.listPrice` | **Charge model dependent:** `recurringFlatFee.listPrice`, `recurringPerUnit.listPrice`, etc. |
| `RatePlanCharge.discountPercentage` | `chargeOverrides[].pricing.{chargeModel}.discountPercentage` | Percentage discount (if applicable to charge model) |
| `RatePlanCharge.discountAmount` | `chargeOverrides[].pricing.{chargeModel}.discountAmount` | Fixed discount amount (if applicable to charge model) |
| `RatePlanCharge.billingPeriod` | `chargeOverrides[].billingPeriod` | Override billing frequency |
| `RatePlanCharge.specificBillingPeriod` | `chargeOverrides[].specificBillingPeriod` | Custom billing period |
| `RatePlanCharge.endDateCondition` | `chargeOverrides[].endDateCondition` | When charge ends |
| `RatePlanCharge.customField__c` | `chargeOverrides[].customField__c` | Custom fields preserved |

**Important:** The `pricing` structure within `chargeOverrides` varies by charge model:
- **Flat Fee**: `pricing.recurringFlatFee.listPrice` (no quantity)
- **Per Unit**: `pricing.recurringPerUnit.quantity` and `listPrice`
- **Tiered**: `pricing.recurringTiered.quantity` and `tiers[]`
- **Volume**: `pricing.recurringVolume.tiers[]` (quantity determined by tier)

### Charge Override Examples by Charge Model

#### Flat Fee Charge Override

```json
{
  "subscribeToRatePlans": [{
    "productRatePlanId": "2c92...",
    "chargeOverrides": [{
      "pricing": {
        "recurringFlatFee": {
          "listPrice": 100.00
        }
      }
    }]
  }]
}
```

#### Per Unit Charge Override (with quantity)

```json
{
  "subscribeToRatePlans": [{
    "productRatePlanId": "2c92...",
    "chargeOverrides": [{
      "pricing": {
        "recurringPerUnit": {
          "listPrice": 10.00,
          "quantity": 5
        }
      }
    }]
  }]
}
```

#### Tiered Charge Override (with quantity)

```json
{
  "subscribeToRatePlans": [{
    "productRatePlanId": "2c92...",
    "chargeOverrides": [{
      "pricing": {
        "recurringTiered": {
          "quantity": 15,
          "tiers": [{
            "tier": 1,
            "startingUnit": 1,
            "endingUnit": 10,
            "price": 30.00
          }, {
            "tier": 2,
            "startingUnit": 11,
            "endingUnit": 20,
            "price": 20.00
          }]
        }
      }
    }]
  }]
}
```

#### Volume Charge Override

```json
{
  "subscribeToRatePlans": [{
    "productRatePlanId": "2c92...",
    "chargeOverrides": [{
      "pricing": {
        "recurringVolume": {
          "tiers": [{
            "tier": 1,
            "startingUnit": 1,
            "endingUnit": 100,
            "price": 1000.00
          }, {
            "tier": 2,
            "startingUnit": 101,
            "endingUnit": 500,
            "price": 4000.00
          }]
        }
      }
    }]
  }]
}
```

## Response Structure Changes

### Subscribe API Response

```json
{
  "success": true,
  "accountId": "2c92a0fd8c7f6e5b018c7f9a12345678",
  "accountNumber": "A00000123",
  "subscriptionId": "2c92a0fd8c7f6e5b018c7f9a98765432",
  "subscriptionNumber": "A-S00000456",
  "invoiceId": "2c92a0fd8c7f6e5b018c7f9a55555555",
  "invoiceNumber": "INV00000789",
  "paymentId": "2c92a0fd8c7f6e5b018c7f9a66666666",
  "totalInvoiceBalance": 100.00,
  "invoiceResult": {
    "invoiceId": "2c92a0fd8c7f6e5b018c7f9a55555555",
    "invoiceNumber": "INV00000789"
  }
}
```

### Order API Response

```json
{
  "success": true,
  "orderNumber": "O-00000123",
  "accountNumber": "A00000123",
  "accountId": "2c92a0fd8c7f6e5b018c7f9a12345678",
  "subscriptions": [{
    "subscriptionNumber": "A-S00000456",
    "subscriptionId": "2c92a0fd8c7f6e5b018c7f9a98765432",
    "status": "Active",
    "orderActions": [{
      "type": "CreateSubscription",
      "sequence": 0
    }]
  }],
  "invoiceNumbers": ["INV00000789"],
  "invoices": [{
    "invoiceNumber": "INV00000789",
    "invoiceId": "2c92a0fd8c7f6e5b018c7f9a55555555",
    "amount": 100.00,
    "status": "Posted"
  }],
  "paymentNumbers": ["P-00000111"],
  "payments": [{
    "paymentNumber": "P-00000111",
    "paymentId": "2c92a0fd8c7f6e5b018c7f9a66666666",
    "amount": 100.00,
    "status": "Processed"
  }]
}
```

### Response Field Mapping

| Subscribe API Response Field | Order API Response Field | Notes |
|------------------------------|--------------------------|-------|
| `accountId` | `accountId` | Same |
| `accountNumber` | `accountNumber` | Same |
| `subscriptionId` | `subscriptions[0].subscriptionId` | Now nested in array |
| `subscriptionNumber` | `subscriptions[0].subscriptionNumber` | Now nested in array |
| `invoiceId` | `invoices[0].invoiceId` | Now nested in array |
| `invoiceNumber` | `invoiceNumbers[0]` or `invoices[0].invoiceNumber` | Multiple locations |
| `paymentId` | `payments[0].paymentId` | Now nested in array |
| `totalInvoiceBalance` | `invoices[0].amount` | Now in invoice object |
| N/A | `orderNumber` | **New field** - unique order identifier |

## Key Differences and Considerations

### 1. Account Creation Logic

**Subscribe API:**
- If `Account.accountKey` is provided → use existing account
- If `Account.accountKey` is not provided → create new account

**Order API:**
- Use `existingAccountNumber` → use existing account
- Use `newAccount` → create new account
- Cannot mix both in same request

### 2. Payment Method Handling

**Subscribe API:**
- Can create payment method for new or existing accounts

**Order API:**
- Can create payment method only for new accounts (via `newAccount.paymentMethod`)
- For existing accounts, must use existing payment method or create separately via Payment Methods API

### 3. Multiple Subscriptions

**Subscribe API:**
- Creates one subscription per call
- Must make multiple API calls for multiple subscriptions

**Order API:**
- Can create multiple subscriptions in one order
- Each subscription can have multiple actions

### 4. Trigger Dates

**Subscribe API:**
- Uses specific date fields: `contractEffectiveDate`, `serviceActivationDate`, `customerAcceptanceDate`

**Order API:**
- Uses flexible `triggerDates` array with named triggers
- Common trigger names:
  - "ContractEffective"
  - "ServiceActivation"
  - "CustomerAcceptance"

### 5. Term Configuration

**Subscribe API:**
- Simple fields: `initialTerm`, `renewalTerm`, `autoRenew`

**Order API:**
- Structured `terms` object with explicit settings
- Must specify `renewalSetting` when `autoRenew` is true
- Options: "RENEW_WITH_SPECIFIC_TERM", "RENEW_TO_EVERGREEN"

### 6. Error Handling

**Subscribe API:**
- Returns single `success` boolean
- Errors in `reasons` array

**Order API:**
- Returns `success` boolean for overall order
- More detailed error information per subscription and action
- Better support for partial success scenarios

## Migration Examples

### Example 1: Simple New Account + Subscription

**Before (Subscribe API):**
```python
import requests

response = requests.post(
    "https://rest.zuora.com/v1/action/subscribe",
    json={
        "Account": {
            "name": "New Customer",
            "currency": "USD",
            "billCycleDay": 1,
            "billToContact": {
                "firstName": "Jane",
                "lastName": "Smith",
                "address1": "456 Oak Ave",
                "city": "Boston",
                "state": "MA",
                "postalCode": "02101",
                "country": "USA",
                "workEmail": "jane@example.com"
            }
        },
        "SubscribeOptions": {
            "generateInvoice": True,
            "processPayments": False
        },
        "SubscriptionData": {
            "Subscription": {
                "termType": "TERMED",
                "contractEffectiveDate": "2026-05-01",
                "initialTerm": 12,
                "autoRenew": True,
                "renewalTerm": 12
            },
            "RatePlanData": [{
                "RatePlan": {
                    "productRatePlanId": "2c92a0fd8c7f6e5b018c7f9a12345678"
                }
            }]
        }
    },
    headers=headers
)

subscription_id = response.json()['subscriptionId']
account_number = response.json()['accountNumber']
```

**After (Order API):**
```python
import requests

response = requests.post(
    "https://rest.zuora.com/v1/orders",
    json={
        "orderDate": "2026-05-01",
        "processingOptions": {
            "runBilling": True,
            "collect": False
        },
        "newAccount": {
            "name": "New Customer",
            "currency": "USD",
            "billCycleDay": 1,
            "billToContact": {
                "firstName": "Jane",
                "lastName": "Smith",
                "address1": "456 Oak Ave",
                "city": "Boston",
                "state": "MA",
                "postalCode": "02101",
                "country": "USA",
                "workEmail": "jane@example.com"
            }
        },
        "subscriptions": [{
            "orderActions": [{
                "type": "CreateSubscription",
                "triggerDates": [{
                    "name": "ContractEffective",
                    "triggerDate": "2026-05-01"
                }],
                "createSubscription": {
                    "terms": {
                        "initialTerm": {
                            "period": 12,
                            "periodType": "Month",
                            "termType": "TERMED"
                        },
                        "autoRenew": True,
                        "renewalSetting": "RENEW_WITH_SPECIFIC_TERM",
                        "renewalTerms": [{
                            "period": 12,
                            "periodType": "Month"
                        }]
                    },
                    "subscribeToRatePlans": [{
                        "productRatePlanId": "2c92a0fd8c7f6e5b018c7f9a12345678"
                    }]
                }
            }]
        }]
    },
    headers=headers
)

subscription_id = response.json()['subscriptions'][0]['subscriptionId']
account_number = response.json()['accountNumber']
order_number = response.json()['orderNumber']
```

### Example 2: Existing Account + Subscription

**Before (Subscribe API):**
```python
response = requests.post(
    "https://rest.zuora.com/v1/action/subscribe",
    json={
        "Account": {
            "accountKey": "A00000001"
        },
        "SubscribeOptions": {
            "generateInvoice": False
        },
        "SubscriptionData": {
            "Subscription": {
                "termType": "EVERGREEN",
                "contractEffectiveDate": "2026-05-01"
            },
            "RatePlanData": [{
                "RatePlan": {
                    "productRatePlanId": "2c92a0fd8c7f6e5b018c7f9a12345678"
                }
            }]
        }
    },
    headers=headers
)
```

**After (Order API):**
```python
response = requests.post(
    "https://rest.zuora.com/v1/orders",
    json={
        "orderDate": "2026-05-01",
        "existingAccountNumber": "A00000001",
        "processingOptions": {
            "runBilling": False
        },
        "subscriptions": [{
            "orderActions": [{
                "type": "CreateSubscription",
                "triggerDates": [{
                    "name": "ContractEffective",
                    "triggerDate": "2026-05-01"
                }],
                "createSubscription": {
                    "terms": {
                        "initialTerm": {
                            "termType": "EVERGREEN"
                        },
                        "autoRenew": False
                    },
                    "subscribeToRatePlans": [{
                        "productRatePlanId": "2c92a0fd8c7f6e5b018c7f9a12345678"
                    }]
                }
            }]
        }]
    },
    headers=headers
)
```

## Common Migration Patterns

### Pattern 0: Detecting Preview vs Create Mode

```python
# Detect if Subscribe API is in preview mode
subscribe_request = {...}

# Check for PreviewOptions presence
has_preview_options = 'PreviewOptions' in subscribe_request and subscribe_request['PreviewOptions']

if has_preview_options:
    # Use Order Preview API
    endpoint = "https://rest.zuora.com/v1/orders/preview"
    
    # Build preview request
    order_request = {
        "orderDate": subscribe_request['SubscriptionData']['Subscription']['contractEffectiveDate'],
        "previewOptions": {
            "previewTypes": ["BillingDocs", "ChargeMetrics"],  # Subscribe API only supports these two
            "previewNumberOfPeriods": subscribe_request['PreviewOptions'].get('numberOfPeriods', 1)
        }
    }
    
    # Handle account info
    if 'accountKey' not in subscribe_request['Account']:
        # New account - use previewAccountInfo
        order_request['previewAccountInfo'] = subscribe_request['Account']
    else:
        # Existing account
        order_request['existingAccountNumber'] = subscribe_request['Account']['accountKey']
    
    # No processingOptions in preview mode
    
else:
    # Use Order Create API
    endpoint = "https://rest.zuora.com/v1/orders"
    
    # Build create request
    order_request = {
        "orderDate": subscribe_request['SubscriptionData']['Subscription']['contractEffectiveDate'],
        "processingOptions": {
            "runBilling": subscribe_request['SubscribeOptions'].get('generateInvoice', False),
            "collect": subscribe_request['SubscribeOptions'].get('processPayments', False)
        }
    }
    
    # Handle account info
    if 'accountKey' not in subscribe_request['Account']:
        # New account - use newAccount
        order_request['newAccount'] = subscribe_request['Account']
    else:
        # Existing account
        order_request['existingAccountNumber'] = subscribe_request['Account']['accountKey']
```

### Pattern 1: Detecting New vs. Existing Account

```python
# In Subscribe API code
if 'accountKey' in subscribe_request['Account']:
    # Using existing account
    account_identifier = subscribe_request['Account']['accountKey']
else:
    # Creating new account
    new_account_data = subscribe_request['Account']

# Convert to Order API
if account_identifier:
    order_request = {
        "existingAccountNumber": account_identifier,
        # ... rest of order
    }
else:
    order_request = {
        "newAccount": new_account_data,
        # ... rest of order
    }
```

### Pattern 2: Converting Term Configuration

```python
# Subscribe API term data
subscription = subscribe_request['SubscriptionData']['Subscription']

# Convert to Order API terms
if subscription['termType'] == 'TERMED':
    terms = {
        "initialTerm": {
            "period": subscription['initialTerm'],
            "periodType": subscription.get('initialTermPeriodType', 'Month'),
            "termType": "TERMED"
        },
        "autoRenew": subscription.get('autoRenew', False)
    }
    
    if subscription.get('autoRenew'):
        terms["renewalSetting"] = "RENEW_WITH_SPECIFIC_TERM"
        terms["renewalTerms"] = [{
            "period": subscription.get('renewalTerm', subscription['initialTerm']),
            "periodType": subscription.get('renewalTermPeriodType', 'Month')
        }]
else:  # EVERGREEN
    terms = {
        "initialTerm": {
            "termType": "EVERGREEN"
        },
        "autoRenew": False
    }
```

### Pattern 3: Converting Charge Overrides

**Important:** The charge override structure depends on the product's charge model. You need to know the charge model type to construct the correct `pricing` structure.

```python
# Subscribe API charge data
charge_data_list = rate_plan_data['RatePlanChargeData']

# Convert to Order API charge overrides
charge_overrides = []
for charge_data in charge_data_list:
    charge = charge_data['RatePlanCharge']
    override = {}
    
    # Note: You need to know the charge model for each product rate plan charge
    # This information should come from product catalog or be specified by user
    # Common charge models: FlatFee, PerUnit, Tiered, Volume
    
    # Example: Assuming Per Unit charge model
    if 'quantity' in charge or 'price' in charge:
        override['pricing'] = {
            "recurringPerUnit": {}
        }
        if 'quantity' in charge:
            override['pricing']['recurringPerUnit']['quantity'] = charge['quantity']
        if 'price' in charge:
            override['pricing']['recurringPerUnit']['listPrice'] = charge['price']
    
    # For Flat Fee charges (no quantity)
    # override['pricing'] = {
    #     "recurringFlatFee": {
    #         "listPrice": charge['price']
    #     }
    # }
    
    # For Tiered charges
    # override['pricing'] = {
    #     "recurringTiered": {
    #         "quantity": charge['quantity'],
    #         "tiers": [...]  # Tier configuration
    #     }
    # }
    
    # Other charge override fields (charge model independent)
    if 'billingPeriod' in charge:
        override['billingPeriod'] = charge['billingPeriod']
    
    if 'discountPercentage' in charge:
        # Add discount to the appropriate pricing model
        if 'pricing' in override:
            for model in override['pricing'].values():
                model['discountPercentage'] = charge['discountPercentage']
    
    charge_overrides.append(override)
```

**Best Practice:** Query the product catalog to determine the charge model before constructing the charge override structure.

### Pattern 4: Using Electronic Payment Method

When the Subscribe API specifies which payment method to use for electronic payment collection via `electronicPaymentMethodId`, this maps to the Order API's `electronicPaymentOptions`.

```python
# Subscribe API with electronicPaymentMethodId
subscribe_request = {
    "Account": {
        "accountKey": "A00000001"  # Existing account with multiple payment methods
    },
    "SubscribeOptions": {
        "generateInvoice": True,
        "processPayments": True,
        "electronicPaymentMethodId": "2c92a0fd8c7f6e5b018c7f9a99999999"  # Specific payment method to use
    },
    "SubscriptionData": {...}
}

# Convert to Order API
order_request = {
    "orderDate": "2026-04-20",
    "existingAccountNumber": "A00000001",
    "processingOptions": {
        "runBilling": True,
        "collect": True
    },
    "electronicPaymentOptions": {
        "paymentMethodId": "2c92a0fd8c7f6e5b018c7f9a99999999"  # Specify which payment method to use
    },
    "subscriptions": [{
        "orderActions": [{
            "type": "CreateSubscription",
            "createSubscription": {...}
        }]
    }]
}
```

**Use Cases:**
- Account has multiple payment methods, need to specify which one to use
- Override default payment method for this specific order
- Use a specific payment method for electronic payment collection when `processingOptions.collect` is true

**Note:** `electronicPaymentOptions` is only applicable when:
- `processingOptions.collect` is set to `true`
- The account has a valid payment method
- The payment method ID is active and belongs to the account

## Validation Checklist

When migrating Subscribe API to Order API:

### General Checks
- [ ] **Detect mode first**: Check if `PreviewOptions` exists to determine preview vs create mode
- [ ] Identify if creating new account or using existing account
- [ ] Set `orderDate` (new required field)

### For Create Mode (no PreviewOptions)
- [ ] Use endpoint: `POST /v1/orders`
- [ ] Map account fields to `newAccount` or `existingAccountNumber`
- [ ] Map `billToContact` fields (required for new accounts)
- [ ] Map `soldToContact` fields (optional, defaults to billToContact)
- [ ] Handle payment method creation (only for new accounts in Order API)
- [ ] Convert `SubscribeOptions` to `processingOptions` (runBilling, collect)
- [ ] If `electronicPaymentMethodId` present: map to `electronicPaymentOptions.paymentMethodId`
- [ ] Update response handling for nested subscription data
- [ ] Handle new `orderNumber` field in response
- [ ] Verify invoice and payment generation behavior

### For Preview Mode (PreviewOptions present)
- [ ] Use endpoint: `POST /v1/orders/preview`
- [ ] For new accounts: use `previewAccountInfo` (NOT `newAccount`)
- [ ] For existing accounts: use `existingAccountNumber` as usual
- [ ] **Required**: Add `previewOptions` with `previewTypes` array
- [ ] Map `PreviewOptions.numberOfPeriods` to `previewOptions.previewNumberOfPeriods`
- [ ] **Do NOT include** `processingOptions` (not applicable in preview mode)
- [ ] Handle preview response structure (different from create response)
- [ ] Verify preview results (billing docs, metrics) match expectations

### Common to Both Modes
- [ ] Map subscription term configuration correctly (TERMED vs EVERGREEN)
- [ ] Convert `initialTerm` and `renewalTerm` to structured `terms` object
- [ ] Set `renewalSetting` when `autoRenew` is true (for TERMED subscriptions)
- [ ] Map contract dates to `triggerDates` array
- [ ] Convert `RatePlanData` to `subscribeToRatePlans`
- [ ] Map charge overrides with correct pricing structure (quantity inside pricing model)
- [ ] Ensure charge override structure matches charge model (FlatFee, PerUnit, Tiered, Volume)
- [ ] Test with sandbox environment before production

## Common Gotchas

### ❌ Incorrect: Payment Method for Existing Account

```json
// This doesn't work - Order API can't create payment methods for existing accounts
{
  "existingAccountNumber": "A00000001",
  "newAccount": {
    "paymentMethod": {
      "type": "CreditCard",
      "cardNumber": "4111111111111111"
    }
  }
}
```

### ✅ Correct: Use Existing Payment Method or Create Separately

```json
// Use existing payment method on the account
{
  "existingAccountNumber": "A00000001",
  "subscriptions": [...]
}

// Or create payment method separately via Payment Methods API first
```

### ❌ Incorrect: Credit Card Field Names

```json
// Old Subscribe API field names don't work in Order API
{
  "newAccount": {
    "paymentMethod": {
      "creditCardNumber": "4111111111111111",  // Wrong
      "creditCardType": "Visa",                 // Wrong
      "creditCardHolderName": "John Doe"        // Wrong
    }
  }
}
```

### ✅ Correct: Order API Field Names

```json
{
  "newAccount": {
    "paymentMethod": {
      "cardNumber": "4111111111111111",     // Correct
      "cardType": "Visa",                   // Correct
      "cardHolderName": "John Doe"          // Correct
    }
  }
}
```

### ❌ Incorrect: Missing Renewal Configuration for TERMED

```json
// Incomplete - TERMED with autoRenew needs renewalSetting and renewalTerms
{
  "terms": {
    "initialTerm": {
      "period": 12,
      "periodType": "Month",
      "termType": "TERMED"
    },
    "autoRenew": true
    // Missing renewalSetting and renewalTerms!
  }
}
```

### ✅ Correct: Complete TERMED Configuration

```json
{
  "terms": {
    "initialTerm": {
      "period": 12,
      "periodType": "Month",
      "termType": "TERMED"
    },
    "autoRenew": true,
    "renewalSetting": "RENEW_WITH_SPECIFIC_TERM",
    "renewalTerms": [{
      "period": 12,
      "periodType": "Month"
    }]
  }
}
```

### ❌ Incorrect: Quantity Directly in chargeOverrides

```json
// Wrong - quantity must be inside the pricing model object
{
  "subscribeToRatePlans": [{
    "productRatePlanId": "2c92...",
    "chargeOverrides": [{
      "quantity": 5  // This is incorrect!
    }]
  }]
}
```

### ✅ Correct: Quantity Inside Pricing Model

```json
// Correct - quantity is inside the appropriate pricing model
{
  "subscribeToRatePlans": [{
    "productRatePlanId": "2c92...",
    "chargeOverrides": [{
      "pricing": {
        "recurringPerUnit": {
          "quantity": 5  // Correct for Per Unit charges
        }
      }
    }]
  }]
}
```

**Note:** The pricing structure depends on the charge model:
- Flat Fee charges don't have a quantity field
- Per Unit charges: `pricing.recurringPerUnit.quantity`
- Tiered charges: `pricing.recurringTiered.quantity`
- Volume charges: quantity is determined by tier ranges

### ❌ Incorrect: Using Wrong Endpoint for Preview Mode

```python
# Wrong - using create endpoint for preview
if 'PreviewOptions' in subscribe_request:
    response = requests.post(
        "https://rest.zuora.com/v1/orders",  # Wrong endpoint!
        json=order_request
    )
```

### ✅ Correct: Using Preview Endpoint

```python
# Correct - using preview endpoint when PreviewOptions present
if 'PreviewOptions' in subscribe_request:
    response = requests.post(
        "https://rest.zuora.com/v1/orders/preview",  # Correct!
        json={
            "orderDate": "2026-05-01",
            "previewOptions": {
                "previewTypes": ["BillingDocs", "ChargeMetrics"]
            },
            "subscriptions": [...]
        }
    )
```

### ❌ Incorrect: Missing previewTypes in Preview Mode

```json
// Wrong - previewTypes is required for Order Preview API
POST /v1/orders/preview
{
  "orderDate": "2026-05-01",
  "previewOptions": {
    "previewNumberOfPeriods": 3
    // Missing previewTypes!
  },
  "subscriptions": [...]
}
```

### ✅ Correct: Including Required previewTypes

```json
// Correct - previewTypes is provided
POST /v1/orders/preview
{
  "orderDate": "2026-05-01",
  "previewOptions": {
    "previewTypes": ["BillingDocs", "ChargeMetrics"],
    "previewNumberOfPeriods": 3
  },
  "subscriptions": [...]
}
```

### ❌ Incorrect: Using newAccount in Preview Mode

```json
// Wrong - should use previewAccountInfo for new accounts in preview
POST /v1/orders/preview
{
  "newAccount": {  // Wrong field name for preview!
    "name": "Example Corp",
    "currency": "USD"
  },
  "previewOptions": {...}
}
```

### ✅ Correct: Using previewAccountInfo in Preview Mode

```json
// Correct - previewAccountInfo for new accounts in preview mode
POST /v1/orders/preview
{
  "previewAccountInfo": {  // Correct for preview mode
    "name": "Example Corp",
    "currency": "USD",
    "billCycleDay": 1
  },
  "previewOptions": {
    "previewTypes": ["BillingDocs"]
  }
}
```

## Additional Resources

- [Order API Documentation](https://www.zuora.com/developer/api-references/api/tag/Orders)
- [Subscribe Action API Documentation](https://developer.zuora.com/v1-api-reference/older-api/actions/action_postsubscribe)
- [Payment Methods API](https://www.zuora.com/developer/api-references/api/tag/Payment-Methods)
- [Order API Best Practices](https://knowledgecenter.zuora.com/)

## Source Code Verification

This mapping has been verified against Zuora Billing source code meta classes:
- `com.zuora.api.action.SubscribeMeta` (Subscribe Action API)
- `com.zuora.rest.meta.order.PostOrderMeta` (Order API)
- `com.zuora.rest.meta.order.PostOrderActionCreateSubscriptionMeta` (CreateSubscription action)
