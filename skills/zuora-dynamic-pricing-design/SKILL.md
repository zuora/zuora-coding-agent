---
name: zuora-dynamic-pricing-design
description: Design a Commerce Catalog setup with dynamic pricing — gather requirements, inspect tenant state, and propose the catalog structure before execution
argument-hint: [product/pricing description or business requirement]
allowed-tools: [Read, Glob, Grep, Bash, Agent, mcp__zuora-mcp__manage_commerce_context_attributes, mcp__zuora-mcp__manage_commerce_charges, mcp__zuora-mcp__query_objects, mcp__zuora-mcp__manage_custom_fields, mcp__zuora-mcp__ask_zuora]
---

You are designing a Commerce Catalog setup with dynamic pricing. Your job is to gather requirements, inspect the tenant's current state, and propose a complete catalog structure — NOT to create anything yet.

## Preflight: Check DynamicPricing is enabled

Before proceeding, call `manage_commerce_charges` with `{"help": true, "operation": "create_charge"}`. If the tool is not available (not listed / not found), stop and tell the user:

> The DynamicPricing feature is not enabled on this tenant. Enable it at **Settings > Billing > Manage Features > Commerce**, then retry.

Note: The Commerce Catalog and Classic Catalog are mutually exclusive.

## Input

The user's request: $ARGUMENTS

## Tool routing

Use `manage_commerce_context_attributes` with `list_attributes` to inspect existing schemas. Use `query_objects` to check existing products, plans, and custom fields. Use `manage_commerce_charges` with `help: true` for charge model guidance. Use `manage_custom_fields` to inspect and create custom field definitions. Use `mcp__zuora-mcp__ask_zuora` only as a fallback for unresolved product-behavior questions (e.g., "can dynamic pricing coexist with discount charges?") after checking the charge help and references first.

## Workflow

### Step 1: Clarify requirements

Determine the scope:
- **Full catalog setup** — new product + plan + charge with dynamic pricing
- **Add dynamic pricing to existing charge** — new attributes and rate cards on an existing charge
- **Update rate card** — modify prices, add attribute values, add rows

For new setups, gather:
- Product name, description, category (`base` or `add-on`)
- Plan name, billing currencies
- Charge model: `flat_fee`, `per_unit`, `tiered`, `volume`, `tiered_overage`, `overage`, `discount_percentage`, `discount_fixed_amount`
- Charge type: `recurring`, `one_time`, `usage`
- What business dimensions drive pricing (e.g., region, customer segment, commitment type, quantity band)
- Expected pricing for each dimension combination
- Default pricing (fallback when no rate card matches)
- Billing cycle preferences
- Unit of measure (for per_unit, tiered, volume, usage charges)

**Product grouping principle:** If the user describes what looks like multiple products that share the same base name but differ by pricing (e.g., "On-Demand" vs "Reserved" vs "Spot"), consolidate them into ONE product with ONE charge that has MULTIPLE rate cards differentiated by attributes. Don't create separate products for pricing variations.

**Attribute mapping level:** Some attributes can validly map to multiple objects (e.g., "Region" could live on Account, RatePlan, or a usage record). When the mapping level is ambiguous, confirm with the user. Choose based on at what granularity the value changes:
- **Account** — fixed per customer, shared across all subscriptions (e.g., customer region, segment)
- **Subscription** — can differ between subscriptions for the same customer (e.g., commitment type: one sub is "reserved", another "on-demand")
- **RatePlan** — set per rate plan instance within a subscription (e.g., service tier chosen for that specific plan)
- **Usage** — varies per event/record (e.g., resource type, cloud region of the API call). Only available on usage charges.

A single charge can combine attributes at different levels (e.g., `CustomerTier` on Account + `ResourceType` on Usage).

### Step 2: Inspect tenant state

#### 2a: Check existing context schemas and attributes

Call `manage_commerce_context_attributes` with `list_attributes` to see what's already configured. Available context schemas include: Business Structure, Catalog, Channel, Custom, Customer Context, Location.

#### 2b: Check mapped fields

Attributes can map to **standard fields** or **custom fields** (`__c` suffix) on multiple Zuora objects. Use `query_objects` with `help: "fields"` and the target `objectType` to discover available fields.

- `account` — standard or custom fields
- `subscription` — standard or custom fields
- `rate_plan` — standard or custom fields
- `usage` — usage record fields

Standard fields already exist — no creation needed. Only custom fields (`__c` suffix) require creation.

**Ambiguous mappings:** When an attribute could reasonably live on multiple objects, ask the user which level to map it at. Explain the granularity:
- **Account** — one value per customer, applies to all subscriptions
- **Subscription** — can vary across subscriptions for the same customer
- **RatePlan** — set per rate plan instance within a subscription
- **Usage** — varies per usage record; only available on usage charges

A single charge can combine attributes at different levels.

If custom fields are needed, use `manage_custom_fields` with `list_custom_fields` to check what exists. Note missing custom fields as prerequisites:
- Object type (Account, Subscription, RatePlan, etc.)
- Field name (must end with `__c`)
- Field type (`string` or `integer`)
- Label and description

#### 2c: Check existing catalog entities

Use `query_objects` to inspect:
- Existing products: `objectType: "Product"`
- Existing rate plans: `objectType: "ProductRatePlan"`
- Existing charges: `objectType: "ProductRatePlanCharge"`

This helps determine whether to create new entities or attach dynamic pricing to existing ones.

### Step 3: Charge model guidance

Call `manage_commerce_charges` with `help: true` to get detailed field requirements, constraints, and examples for the chosen charge model.

Key model decisions:
- **flat_fee** — fixed amount per period (simplest)
- **per_unit** — price × quantity (per seat, per license)
- **tiered** — progressive tiers (first N at price A, next M at price B)
- **volume** — all units priced at the tier reached by total quantity
- **tiered_overage** — included units + tiered overage pricing
- **overage** — simple per-unit overage rate
- **discount_percentage** / **discount_fixed_amount** — discounts applied to other charges

### Step 4: Propose the design

Present a structured proposal:

```
## Dynamic Pricing Design

### Prerequisites
- [ ] Custom fields to create:
  | Object | Field Name | Type | Description | Example Values |
  |--------|-----------|------|-------------|----------------|
  | Account | Region__c | String | Customer region | US, EU, APAC |

- [ ] Context attributes to create: [list new attributes needed]

### Context Attributes
| Attribute | Schema | Type | Mapped Object.Field | Valid Values |
|-----------|--------|------|---------------------|--------------|
| Region | location | STRING | Account.Region__c | US, EU, APAC |
| CommitmentType | custom | STRING | Subscription.CommitmentType__c | on-demand, reserved |

### Product
- Name: ...
- Category: base | add-on
- Dates: startDate → endDate

### Plan
- Name: ...
- Currencies: [USD, ...]

### Charge
- Name: ...
- Model: per_unit
- Type: recurring
- Bill cycle: default_from_customer / monthly / in_advance
- Trigger: contract_effective
- End date condition: subscription_end
- Unit of measure: (if applicable)
- Default pricing: $X.XX (applies when no rate card matches)

### Rate Card
| Region | CommitmentType | Price (USD) |
|--------|---------------|-------------|
| US | on-demand | $10.00 |
| US | reserved | $7.00 |
| EU | on-demand | $8.00 |
| EU | reserved | $5.50 |

### Rate Card Operators
- Region: == (exact match)
- CommitmentType: == (exact match)

### Constraints
- [any edge cases, limitations, or decisions to confirm]
```

### Step 5: Confirm with user

Use AskUserQuestion to confirm the design before proceeding. If confirmed, suggest running `/zuora-dynamic-pricing-build` to execute.

## Key constraints to surface in design

- `productRatePlanId` cannot be changed after charge creation
- Tiered pricing: ranges must not overlap; last tier omits `upTo` (unbounded) — EXCEPT `tiered_overage` where ALL tiers require `upTo`
- Rate card operators: `==`, `>`, `>=`, `<`, `<=`, `between`, `between-inclusive`, `matches` (regex). NOT supported: `!=`
- For `between`/`between-inclusive`, value is an array: `[lower, upper]`
- Attribute types: `String`, `Integer`, `Double` (NOT Decimal), `Boolean`, `Date`, `Datetime`
- Usage charges must NOT include `billCycle.timing`; recurring/one_time SHOULD include it (`in_advance` or `in_arrears`)
- First matching rate card wins; if no rate card matches, default pricing applies
- Mapped fields must exist before attribute creation (standard fields already exist; custom fields must be created first)
- Consolidate pricing variations into rate cards on a single charge — don't create separate products for each price point
