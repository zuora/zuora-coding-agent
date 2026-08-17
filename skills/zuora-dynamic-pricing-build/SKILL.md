---
name: zuora-dynamic-pricing-build
description: Execute a Commerce Catalog dynamic pricing setup — create custom fields, attributes, products, plans, charges, and rate cards on the tenant
argument-hint: [design reference or direct instructions]
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash, Agent, mcp__zuora-mcp__manage_commerce_products, mcp__zuora-mcp__manage_commerce_plans, mcp__zuora-mcp__manage_commerce_charges, mcp__zuora-mcp__manage_commerce_context_attributes, mcp__zuora-mcp__manage_custom_fields, mcp__zuora-mcp__query_objects, mcp__zuora-mcp__ask_zuora]
---

You are executing a Commerce Catalog dynamic pricing setup directly on the user's Zuora tenant. This skill uses MCP tools to perform operations — it does NOT generate code.

## Preflight: Check DynamicPricing is enabled

Before proceeding, call `manage_commerce_charges` with `{"help": true, "operation": "create_charge"}`. If the tool is not available (not listed / not found), stop and tell the user:

> The DynamicPricing feature is not enabled on this tenant. Enable it at **Settings > Billing > Manage Features > Commerce**, then retry.

## Input

The user's request: $ARGUMENTS

This could be:
- A reference to a design from `/zuora-dynamic-pricing-design`
- Direct instructions to create/update catalog entities
- A request to update rate card prices or add new rows/attribute values

If the input is a raw business requirement (not a confirmed design artifact), **stop and ask the user to run `/zuora-dynamic-pricing-design` first** so the design can be reviewed and approved before any catalog mutations occur. Only proceed directly when the user supplies a previously approved design or gives explicit, self-contained build instructions.

## Tool routing

- `manage_commerce_context_attributes` — create/update context attributes
- `manage_commerce_products` — create/update/delete products (can include plans and charges in one call)
- `manage_commerce_plans` — create/update/delete plans
- `manage_commerce_charges` — create/update/delete/query charges, update tier prices. Use `help: true` for per-operation guidance before calling.
- `manage_custom_fields` — list/add/update custom field definitions on standard Zuora objects
- `query_objects` — look up existing entities, tier IDs, custom field definitions
- `mcp__zuora-mcp__ask_zuora` — only as a fallback for unresolved product-behavior questions after checking charge help first

## Workflow

### Step 0: Ensure mapped fields exist

Attributes can map to **standard fields** or **custom fields** (`__c` suffix). Standard fields already exist — only custom fields need creation.

To discover available fields on an object, call `query_objects` with `help: "fields"` and the target `objectType`.

Attributes can map to fields on multiple objects:
- `Account` — standard or custom fields
- `Account.BillToContact` — fields from the bill-to contact on the account
- `Account.SoldToContact` — fields from the sold-to contact on the account
- `Subscription` — standard or custom fields
- `RatePlan` — standard or custom fields
- `Usage` — usage record fields (preferred for usage charges)

**Mapping level:** If the design doesn't specify the mapping object for an attribute, confirm with the user before proceeding. Choose based on at what granularity the value changes:
- `account` — fixed per customer, shared across all subscriptions
- `subscription` — can differ between subscriptions for the same customer
- `rate_plan` — set per rate plan instance within a subscription
- `usage` — varies per event/record (only available on usage charges)

**If custom fields are needed**, use `manage_custom_fields` to add them. First call `list_custom_fields` with the target `objectType` to check what exists, then `add_custom_field` for each missing field:
- `objectType` — e.g., `Account`, `Subscription`, `RatePlan`
- `fieldName` — must end with `__c` (auto-appended if omitted)
- `label` — display name in Zuora UI
- `fieldType` — `string` or `integer` (default: `string`)

Confirm each custom field was created successfully before proceeding.

### Step 1: Setup context attributes

Create or update context attributes that drive dynamic pricing.

**List existing:**
```
Tool: manage_commerce_context_attributes
operation: list_attributes
```

**Create new attribute (custom field mapping):**
```
Tool: manage_commerce_context_attributes
operation: create_attribute
contextSchemaId: "location"
attributeJson: {
  "slug": "region",
  "name": "Region",
  "type": "STRING",
  "mapping": [{
    "slug": "zuora-region",
    "sourceSystem": "zuora",
    "path": "Account.Region__c",
    "validValues": {"stringValues": ["US", "EU", "APAC"]}
  }]
}
```

**Create attribute mapped to standard field:**

First use `query_objects` with `help: "fields"` and `objectType: "Account"` to confirm the standard field name, then:
```
Tool: manage_commerce_context_attributes
operation: create_attribute
contextSchemaId: "customer_context"
attributeJson: {
  "slug": "currency",
  "name": "Currency",
  "type": "STRING",
  "mapping": [{
    "slug": "zuora-currency",
    "sourceSystem": "zuora",
    "path": "Account.Currency",
    "validValues": {"stringValues": ["USD", "EUR", "GBP"]}
  }]
}
```

**Add new values to existing attribute:**
```
Tool: manage_commerce_context_attributes
operation: update_attribute_values
contextSchemaId: "location"
attributeSlug: "region"
... (add new valid values)
```

### Step 2: Create product

Two approaches available:

**Option A — Product only (then plan and charge separately):**
```
Tool: manage_commerce_products
operation: create_product
productJson: {
  "name": "Product Name",
  "description": "...",
  "startDate": "2026-01-01",
  "endDate": "2099-12-31",
  "category": "base"
}
```

**Option B — Full hierarchy in one call (product + plans + charges):**
```
Tool: manage_commerce_products
operation: create_product
productJson: {
  "name": "Product Name",
  "startDate": "2026-01-01",
  "endDate": "2099-12-31",
  "category": "base",
  "plans": [{
    "name": "Standard Plan",
    "startDate": "2026-01-01",
    "endDate": "2099-12-31",
    "activeCurrencies": ["USD"],
    "charges": [{
      "name": "Per-Seat Charge",
      "chargeType": "recurring",
      "chargeModel": "per_unit",
      "unitOfMeasure": "seat",
      "billCycle": {
        "type": "default_from_customer",
        "period": "bill_cycle_period_month",
        "periodAlignment": "align_to_charge",
        "timing": "in_advance"
      },
      "triggerEvent": "contract_effective",
      "endDateCondition": "subscription_end",
      "pricing": {"unitAmounts": {"USD": 10.00}}
    }]
  }]
}
```

Save the returned product `id` and plan `id` for subsequent operations.

**Product grouping:** Pricing variations (on-demand vs reserved, US vs EU) should be rate cards on a SINGLE charge — NOT separate products. Create one product, one plan, one charge with multiple rate cards.

### Step 3: Create plan (if using Option A)

```
Tool: manage_commerce_plans
operation: create_plan
planJson: {
  "productKey": "<product-id>",
  "name": "Plan Name",
  "startDate": "2026-01-01",
  "endDate": "2099-12-31",
  "activeCurrencies": ["USD"]
}
```

**Constraint:** Plan `startDate` must be >= parent product's `startDate`.

### Step 4: Create charge with dynamic pricing

Before creating a charge, call `manage_commerce_charges` with `help: true` to get field guidance for the chosen operation.

**Required fields for all charges:**
- `charge.name` — display name
- `charge.chargeType` — `recurring`, `one_time`, or `usage`
- `charge.chargeModel` — pricing model enum
- `charge.productRatePlanId` — plan ID from step 2/3
- `charge.billCycle.type` — e.g., `default_from_customer`
- `charge.billCycle.period` — e.g., `bill_cycle_period_month`
- `charge.billCycle.periodAlignment` — `align_to_charge`
- `charge.billCycle.timing` — `in_advance` or `in_arrears` (**OMIT for usage charges**)
- `charge.triggerEvent` — `contract_effective`, `service_activation`, or `customer_acceptance`
- `charge.endDateCondition` — `subscription_end`

**Model-specific required fields:**

| Model | Additional required |
|-------|---------------------|
| flat_fee | `pricing.flatAmounts` (map: `{"USD": 99.99}`) |
| per_unit | `pricing.unitAmounts`, `unitOfMeasure`, `defaultQuantity` |
| tiered | `pricing.tiers`, `pricing.tierMode`, `unitOfMeasure` |
| volume | `pricing.tiers`, `pricing.tierMode`, `unitOfMeasure` |
| tiered_overage | `pricing.tiers` (ALL need `upTo`), `pricing.unitAmounts`, `unitOfMeasure` |
| overage | `pricing.unitAmounts`, `unitOfMeasure` |
| discount_percentage | `pricing.discountPercentages`, `discountOptions` |
| discount_fixed_amount | `pricing.discountAmounts`, `discountOptions` |

**Adding dynamic pricing (attributes + rate cards):**

```
Tool: manage_commerce_charges
operation: create_charge
chargeJson: {
  "charge": {
    "name": "Dynamic Per-Unit Charge",
    "chargeType": "recurring",
    "chargeModel": "per_unit",
    "productRatePlanId": "<plan-id>",
    "billCycle": {
      "type": "default_from_customer",
      "period": "bill_cycle_period_month",
      "periodAlignment": "align_to_charge",
      "timing": "in_advance"
    },
    "triggerEvent": "contract_effective",
    "endDateCondition": "subscription_end",
    "unitOfMeasure": "seat",
    "defaultQuantity": 1,
    "pricing": {"unitAmounts": {"USD": 10.00}},
    "attributes": [
      {
        "name": "Region",
        "type": "String",
        "mapping": {"object": "account", "field": "Region__c"}
      }
    ],
    "rateCards": [
      {
        "attributes": [
          {"name": "Region", "operator": "==", "value": {"stringValue": "US"}}
        ],
        "pricing": {"unitAmounts": {"USD": 10.00}}
      },
      {
        "attributes": [
          {"name": "Region", "operator": "==", "value": {"stringValue": "EU"}}
        ],
        "pricing": {"unitAmounts": {"USD": 8.00}}
      }
    ]
  }
}
```

**Attribute declaration:**
- `name` — attribute display name
- `type` — `String`, `Integer`, `Double` (NOT Decimal), `Boolean`, `Date`, `Datetime`
- `mapping.object` — `account`, `account.billtocontact`, `account.soldtocontact`, `subscription`, `rate_plan`, or `usage` (choose by granularity: account = per-customer, subscription = per-sub, rate_plan = per-plan instance, usage = per-event)
- `mapping.field` — field name on that object: standard (e.g., `Country`, `WorkEmail`) or custom (e.g., `Region__c`)
- For contact sub-objects, the `path` in the attribute mapping JSON uses dot notation: `Account.BillToContact.FieldName` or `Account.SoldToContact.FieldName`

**Default pricing:** The `pricing` field at charge level is the fallback when no rate card matches. Always include it.

**Rate card value wrappers (CRITICAL):**
- String: `{"stringValue": "us"}`
- Integer: `{"intValue": 42}`
- Double: `{"numberValue": 9.99}`
- Boolean: `{"boolValue": true}`
- Datetime (used for `EffectiveDate`): `{"stringValue": "2026-04-01T00:00:00Z"}` — ISO-8601 with a zone offset

**Supported operators:** `==`, `>`, `>=`, `<`, `<=`, `between`, `between-inclusive`, `matches` (regex). NOT supported: `!=`.
- For `between`/`between-inclusive`, value is an array: `[lower, upper]`
- First matching rate card wins
- `EffectiveDate` is a reserved attribute and accepts ONLY the `>=` operator (see the effective dating section below)

### Effective dating (time-varying pricing)

Rate cards support effective dating so a price can change on a future date while the prior price is preserved as history. This is driven by a **reserved attribute named `EffectiveDate`**:

- Do NOT declare `EffectiveDate` in the charge-level `attributes[]` array, and do NOT create a custom field or `mapping` for it. It is a reserved attribute the system understands — you only reference it inside a rate card's `attributes[]` criteria.
- On a rate card row, `EffectiveDate` uses operator `>=` only (marks the row's effective-from instant). Any other operator is rejected.
- The value is a `Datetime` wrapped as `{"stringValue": "..."}` in ISO-8601 with a zone offset, e.g. `2026-04-01T00:00:00Z` or `2026-04-01T00:00:00-08:00`. A bare local datetime (no offset) is rejected.
- If a rate card row omits `EffectiveDate`, it is treated as effective from now.

**Set an initial effective-from date on a rate card row:**
```
{
  "attributes": [
    {"name": "Region", "operator": "==", "value": {"stringValue": "US"}},
    {"name": "EffectiveDate", "operator": ">=", "value": {"stringValue": "2026-01-01T00:00:00Z"}}
  ],
  "pricing": {"unitAmounts": {"USD": 10.00}}
}
```

**Schedule a future price change (preserve history):** submit a new row for the SAME business attributes with a later `EffectiveDate`. Do NOT delete the old row — the system automatically closes the previous price to a bounded window ending 1 second before the new start, and the new row becomes the open-ended current price.
```
"rateCards": [
  {
    "attributes": [
      {"name": "Region", "operator": "==", "value": {"stringValue": "US"}},
      {"name": "EffectiveDate", "operator": ">=", "value": {"stringValue": "2026-01-01T00:00:00Z"}}
    ],
    "pricing": {"unitAmounts": {"USD": 10.00}}
  },
  {
    "attributes": [
      {"name": "Region", "operator": "==", "value": {"stringValue": "US"}},
      {"name": "EffectiveDate", "operator": ">=", "value": {"stringValue": "2026-04-01T00:00:00Z"}}
    ],
    "pricing": {"unitAmounts": {"USD": 12.00}}
  }
]
```
Resulting timeline: US → $10.00 for `[2026-01-01, 2026-03-31T23:59:59]`, then US → $12.00 from `2026-04-01` onward.

Notes:
- Rows are grouped by their business attributes only (`EffectiveDate` is excluded from the grouping key), so each dimension combination carries an independent timeline.
- Two rows with the same business attributes AND the same effective date are a duplicate and will be rejected.
- Re-submitting a row whose pricing equals the price already in effect at its effective date is a no-op and is dropped — it will not add a redundant row.

### Step 5: Verify creation

**Query charge metadata with pagination:**

Rate cards default to 10 rows per page. Always use `rateCardPagination` to retrieve all rows:
```
Tool: manage_commerce_charges
operation: query_charge
queryJson: {
  "productRatePlanChargeKey": "<charge-id>",
  "rateCardPagination": {"page": 1, "pageSize": 50}
}
```

If the charge has more rows than `pageSize`, paginate through all pages to get the complete rate card.

**Test dynamic pricing evaluation** (use plain values, NOT wrapped):
```
Tool: manage_commerce_charges
operation: query_charge
queryJson: {
  "productRatePlanChargeKey": "<charge-id>",
  "attributes": [{"name": "Region", "value": "US"}]
}
```

Report the created entity IDs and confirm pricing evaluates correctly.

## Updating existing rate cards

### Update prices

1. Get tier IDs:
```
Tool: query_objects
objectType: "ProductRatePlanChargeTier"
filter: ["ProductRatePlanChargeId.EQ:<charge-id>"]
fields: ["Id", "Tier", "Price", "Currency"]
```

2. Update price:
```
Tool: manage_commerce_charges
operation: update_tier_price
tierJson: {"id": "<tier-id>", "price": 12.50}
```

### Add a new value option to an existing attribute (BCS)

1. Call `manage_commerce_context_attributes` with `update_attribute_values` to add the new valid value.
2. Then update the charge to add a new rate card row (see below).

### Add a new row to the rate card

First query the existing rate cards with pagination to get all rows:
```
Tool: manage_commerce_charges
operation: query_charge
queryJson: {
  "productRatePlanChargeKey": "<charge-id>",
  "rateCardPagination": {"page": 1, "pageSize": 50}
}
```

Then call `manage_commerce_charges` with `update_charge`, providing the full updated `rateCards[]` array including existing rows plus the new one:
```
Tool: manage_commerce_charges
operation: update_charge
chargeJson: {
  "charge": {
    "id": "<charge-id>",
    "rateCards": [
      ... existing rows ...,
      {
        "attributes": [
          {"name": "Region", "operator": "==", "value": {"stringValue": "LATAM"}}
        ],
        "pricing": {"unitAmounts": {"USD": 7.00}}
      }
    ]
  }
}
```

### Change a price effective a future date

To change the price of an EXISTING attribute combination on a schedule (rather than adding a new dimension value), add a new rate card row for the same business attributes with a later `EffectiveDate` — see the effective dating section above. Keep the existing rows in the submitted `rateCards[]`; the system truncates the prior price window automatically and preserves it as history. Do not use `update_tier_price` for scheduled changes — that overwrites the current price in place with no history.

## Critical constraints

- `pricing.flatAmounts` is a map `{"USD": 99.99}`, NOT an array
- Tiered: ranges must not overlap; last tier omits `upTo` — EXCEPT `tiered_overage` where ALL tiers require `upTo`
- Cannot change `productRatePlanId` after charge creation
- Tier IDs NOT returned in charge create/query — must use `query_objects` on `ProductRatePlanChargeTier`
- `billCycle.timing`: include for recurring/one_time (`in_advance` or `in_arrears`), OMIT for usage
- `billCycle.periodAlignment`: use `align_to_charge`
- `endDateCondition`: required, typically `subscription_end`
- For `update_charge`, use `fieldsToNull` array to explicitly clear fields
- Rate card `attributes` array in criteria (NOT `attribute_values` or `criteria`)
- Rate card values use `catalog.Value` wrappers; `query_charge` evaluation uses plain values
- Mapped fields must exist on the object before attribute creation (standard fields already exist; custom fields must be created first)
- Execute in order: custom fields (if needed) → context attributes → product → plan → charge
- Consolidate pricing variations into rate cards — don't create separate products
- `EffectiveDate` is a reserved attribute — never declare it in charge-level `attributes[]`, never map it to a field, never create a custom field for it; use it only inside a rate card's `attributes[]` criteria
- `EffectiveDate` accepts only the `>=` operator; value must be ISO-8601 with a zone offset (e.g. `2026-04-01T00:00:00Z`); omitting it means effective from now
- For a scheduled price change, add a new effective-dated row for the same attributes and keep the existing rows — the system computes the end of the prior window; do not delete old rows or use `update_tier_price`
- Same business attributes + same effective date across two rows is a duplicate (rejected); a row identical in price to what's already in effect is dropped as a no-op
