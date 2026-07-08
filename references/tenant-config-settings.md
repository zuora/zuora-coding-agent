# Zuora Tenant Configuration Settings Reference

This reference catalogs all Zuora Settings API keys, their payload structures, field names, value types, and collection handling patterns. Use this together with `manage_settings` (`get_settings` and `update_settings`) when configuring a Zuora tenant.

## How to use `manage_settings`

The tool exposes three operations, all backed by the Zuora Settings batch API:

| Operation | HTTP | Use for |
|-----------|------|---------|
| `list_setting_keys` | — | Discover all available setting key paths (cached 24h) |
| `get_settings` | GET | Read current value before any change |
| `update_settings` | PUT | Modify an existing setting or collection item |
| `create_settings` | POST | Create a new collection item |

```
Tool: manage_settings
operation: get_settings
settingKey: /billing-rules
```

```
Tool: manage_settings
operation: update_settings
settingKey: /billing-rules
settingValueJson: { ... }
```

```
Tool: manage_settings
operation: create_settings
settingKey: /payment-terms
settingValueJson: { ... }
```

**Always retrieve first.** The current value reveals the live schema, existing item IDs, and default field values before you send an update or create. Only send fields you intend to set; omit read-only or irrelevant fields.

**`settingValueJson` must always be a JSON object `{...}`**, never a bare array. Wrap array-valued payloads: `{"items": [...]}`.

---

## Section: Z_Billing

### `/billing-rules` (SINGLETON)

Controls billing calculation behaviour for the tenant.

| Field | Type | Notes |
|-------|------|-------|
| `availableToCreditValidationLevel` | enum | `HeaderLevel`, `HeaderAndItemLevel`, `None` |
| `creditMemoMirroringInvoiceItemsRule` | enum | `YesExceptForZeroItems`, `Yes`, `No` |
| `catchUpBillRun` | boolean | Enable catch-up bill runs |
| `customerHierarchy` | boolean | Enable customer hierarchy |
| `taxAddressOwner` | enum | `SubscriptionOwner`, `InvoiceOwner` |
| `daysInMonth` | enum | `Assume30Days`, `UseActualDays`, `Assume30DaysStrict` |
| `invoiceDeliveryPrefsBatch` | boolean | |
| `invoiceItemSettlement` | boolean | |
| `prorate` | enum | `FullMonth`, `ActualDays`, `None` |
| `billCycleType` | enum | `DefaultFromCustomer`, `SubscriptionStartDay`, `ChargeTriggerDay`, `SpecificDayofMonth`, `SpecificDayofWeek` |
| `autoPost` | boolean | |
| `consolidatedInvoice` | boolean | |
| `applyCredit` | boolean | |
| `applyCreditBalance` | boolean | |
| `applyUnappliedPaymentToAmendments` | boolean | |
| `creditMemoReasonRequired` | boolean | |
| `debitMemoReasonRequired` | boolean | |

### `/subscription-settings` (SINGLETON)

Default subscription and order settings.

| Field | Type | Notes |
|-------|------|-------|
| `termType` | enum | `TERMED`, `EVERGREEN` |
| `initialTerm` | integer | 0–999 months |
| `renewalTerm` | integer | 0–999 months |
| `contractRenewal` | boolean | Auto-renew default |
| `orderMetricsTaxationOption` | enum | `YES`, `NO`, `ONLY_FOR_TAX_INCLUSIVE_CHARGES` |
| `enableOrdersUIDateValidation` | boolean | |
| `fullProductFeaturedEnabled` | boolean | |
| `quantityValidationOnVolumeCharge` | boolean | |

### `/payment-terms` (COLLECTION — multiple items)

Payment terms are a collection. Retrieve returns an array; update sends the full array.

Per-item fields:

| Field | Type | Notes |
|-------|------|-------|
| `name` | string | Required; must be unique |
| `isActive` | boolean | |
| `isDefault` | boolean | |
| `intervalNumber` | integer | Net days (e.g. 30 for Net 30) |
| `type` | enum | `NetPaymentTerm`, `ProxPaymentTerm` |
| `paymentDueDay` | integer | ProxPaymentTerm only |
| `invoiceCutoffDay` | integer | ProxPaymentTerm only |

**Pattern:** Retrieve returns `{ "paymentTerms": [...] }`. To create, POST to `/payment-terms`; to update, PUT to `/payment-terms/{id}`. With `manage_settings`, use `get_settings` to discover existing IDs, then `update_settings` with the item.

### `/currencies` (COLLECTION — full array replace)

Payload wraps items in `{ "items": [...] }`.

Per-item fields:

| Field | Type | Notes |
|-------|------|-------|
| `currencyCode` | string | ISO alphabetic code (uppercase) |
| `active` | boolean | |
| `default` | boolean | Only one may be default |
| `roundingMode` | enum | `Up`, `Down`, `HalfUp` |
| `roundingIncrement` | number | |
| `rate` | number | Exchange rate |

### `/doc-prefixes` (SINGLETON — document sequence sets)

Only the first sequence set (index 0) is settable via API.

| Field | Type | Notes |
|-------|------|-------|
| `invoice` | object | `{ "prefix": "INV-", "startNum": 1 }` |
| `paymentPrefix` | object | `{ "prefix": "PAY-", "startNum": 1 }` |
| `refundPrefix` | object | `{ "prefix": "REF-", "startNum": 1 }` |
| `creditMemo` | object | `{ "prefix": "CM-", "startNum": 1 }` |
| `debitMemo` | object | `{ "prefix": "DM-", "startNum": 1 }` |

### `/discount-settings` (SINGLETON)

Discount calculation and stacking rules.

### `/charge-types-models` (SINGLETON)

Enabled charge types and charge models.

### `/billing-periods` (SINGLETON)

Supported billing period definitions.

### `/number-and-sku` (SINGLETON)

Auto-generated number and SKU settings.

### `/taxation-codes` (COLLECTION)

Tax codes used in billing.

### `/units-of-measure` (COLLECTION)

Units of measure for usage charges.

### `/revenue-recognition-codes` (COLLECTION)

Revenue recognition rule codes.

---

## Section: Z_Payments

### `/payment-rules` (SINGLETON)

| Field | Type | Notes |
|-------|------|-------|
| `enableCreditCardDateValidation` | boolean | Validate card expiry on payment |

### `/payment-gateways` (COLLECTION — update only, no create via API)

Gateways must be provisioned separately; they can only be updated here.

Per-item fields:

| Field | Type | Notes |
|-------|------|-------|
| `paymentGatewayType` | string | Gateway type identifier |
| `gatewayName` | string | Max 40 characters |
| `active` | boolean | |

**Pattern:** Retrieve to get gateway IDs, then update individual gateways by ID.

### `/payment-retry-rules` (SINGLETON)

Retry schedule configuration for failed payments.

### `/hosted-payment-pages` (COLLECTION)

Hosted payment page (HPM v1) definitions.

### `/payment-pages-hpm2` (COLLECTION)

Hosted payment page v2 definitions.

### `/payment-methods` (SINGLETON/COLLECTION)

Enabled payment method types.

### `/cit-mit-configuration` (SINGLETON)

Customer-initiated vs merchant-initiated transaction (CIT/MIT) configuration.

### `/gateway-reconciliation-config` (SINGLETON)

Gateway reconciliation settings.

### `/real-time-reconciliation` (SINGLETON)

Real-time payment reconciliation settings.

### `/reason-codes` (COLLECTION)

Payment reason codes.

### `/manage-features` (SINGLETON)

Feature flags for the payments module.

---

## Section: Z_Finance

### `/accounting-rules` (SINGLETON)

| Field | Type | Notes |
|-------|------|-------|
| `allowBlankAccountingCodes` | boolean | |
| `allowCreationInClosedPeriod` | boolean | Allow subscriptions/amendments in closed periods |
| `allowUsageInClosedPeriod` | boolean | Allow usage records in closed periods |
| `allowRevenueScheduleNegativeAmounts` | boolean | Allow negative amounts in open-ended period |
| `differentCurrencies` | boolean | Aggregate multi-currency transactions in journal runs |

### `/accounting-code-settings` (SINGLETON)

Default accounting code assignments.

### `/currency-conversion` (SINGLETON)

Currency conversion configuration.

### `/aging-balance-settings` (SINGLETON)

Aging bucket configuration for AR reporting.

### `/chart-of-accounts` (COLLECTION)

Chart of accounts definitions.

### `/revenue-recognition-rules` (via `/revenue-recognition-rules` settingKey)

Revenue recognition rule settings.

---

## Section: Tenant Admin

### `/entity-profile-info` (SINGLETON)

Tenant entity profile and branding.

| Field | Type | Notes |
|-------|------|-------|
| `email` | string | |
| `address1` | string | |
| `city` | string | |
| `state` | string | |
| `postalCode` | string | |
| `country` | string | |
| `locale` | enum | `en_US`, `en_GB`, `fr_FR`, `de_DE`, `ja_JP`, `zh_CN` |
| `bannerColor` | enum | `Rose`, `Teal`, `Aqua`, `Navy`, `Blue_Grey` |
| `bannerLabel` | string | Text shown in the environment banner |
| `displayEnvironmentBanner` | boolean | |

**Non-settable (read-only):** `tenantId`, `tenantName`, `tenantStatus`, `timeZone`, `storageLimit`, `availableStorage`, `maximumNumberOfAttachmentsPerRecord`, `csvInjectionPolicy`

### `/security-policies` (SINGLETON)

| Field | Type | Notes |
|-------|------|-------|
| `passwordComplexityRequirement` | enum | `None`, `Characters`, `ContainAll` |
| `enforcePasswordHistory` | integer | Accepted values: `0`, `4`, `7` |
| `passwordExpiration` | integer | Days: `0` (never), `30`, `60`, `90` |
| `minimumPasswordLength` | integer | Accepted values: `7`, `8`, `10`, `12` |
| `maximumInvalidLoginAttempts` | integer | Range: 3–10 |
| `lockoutEffectivePeriod` | integer | Minutes: `20`, `30`, `60` |
| `sessionTimeout` | integer | Minutes: `15`, `30`, `60`, `120`, `240`, `480` |
| `twoFactor` | boolean | Two-factor authentication |

**Non-settable (read-only):** `publicKey`

### `/oauth-providers` (COLLECTION)

OAuth provider configurations.

### `/api-versioning` (SINGLETON)

Default API version settings.

### `/aqua-time-offset` (SINGLETON)

AQuA query time offset configuration.

---

## Custom Fields (all sections)

Use `mcp__zuora-mcp__manage_custom_fields` (not `manage_settings`) for adding or listing custom fields. The `manage_settings` tool does not cover custom object/field creation.

---

## Collection vs Singleton patterns

| Pattern | Example | How to update | How to create new item |
|---------|---------|---------------|----------------------|
| **SINGLETON** | `/billing-rules` | Retrieve → modify needed fields → `update_settings` | N/A — only one instance |
| **FULL ARRAY REPLACE** | `/currencies` | Retrieve full list → include ALL items (modified + unchanged) → `update_settings` | Add item to the full array in the PUT |
| **ITEM-BY-ID** | `/payment-terms` | Retrieve to get IDs → `update_settings` with key `/payment-terms/{id}` | `create_settings` with key `/payment-terms` |
| **ITEM-BY-ID, update only** | `/payment-gateways` | Retrieve to get IDs → `update_settings` with key `/payment-gateways/{id}` | Not supported — gateway provisioning is external |

> For FULL ARRAY REPLACE settings, omitting an existing item from the payload may delete or deactivate it. Always retrieve first and include unchanged items.

---

## Discover all available setting keys

Use `references/settings-schema.json` (bundled in this plugin) to look up available setting paths and their field schemas. If a key is not found there, first check whether the field is marked `ui_only: true` in `settings-fields.json` — if so, it is a UI-only field and should be skipped entirely (not looked up). Only fall back to `list_setting_keys` if the key is absent from both files:

```
Tool: manage_settings
operation: list_setting_keys
```

Returns a `settingKeys` array of all paths available on the connected tenant.
