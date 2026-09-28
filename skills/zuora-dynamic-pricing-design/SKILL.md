---
name: zuora-dynamic-pricing-design
description: Design a Commerce Catalog setup with dynamic pricing — gather requirements, inspect tenant state, and propose the catalog structure before execution
argument-hint: [product/pricing description, business requirement, and/or CSV/spreadsheet path]
allowed-tools: [Read, Glob, Grep, Bash, Agent, mcp__zuora-mcp__manage_commerce_context_attributes, mcp__zuora-mcp__manage_commerce_charges, mcp__zuora-mcp__query_objects, mcp__zuora-mcp__manage_custom_fields, mcp__zuora-mcp__ask_zuora]
---

You are designing a Commerce Catalog setup with dynamic pricing. Your job is to gather requirements, inspect the tenant's current state, and propose a complete catalog structure — NOT to create anything yet.

## Preflight: Check DynamicPricing is enabled

Before proceeding, call `manage_commerce_charges` with `{"help": true, "operation": "create_charge"}`. If the tool is not available (not listed / not found), stop and tell the user:

> The DynamicPricing feature is not enabled on this tenant. Enable it at **Settings > Billing > Manage Features > Commerce**, then retry.

Note: The Commerce Catalog and Classic Catalog are mutually exclusive.

## Input

The user's request: $ARGUMENTS

Input may be free-text requirements, an approved prior design, **and/or a CSV / spreadsheet path or attachment**. Treat any tabular price file as design input — do not assume a fixed vendor schema (column names, product families, or MSP layouts vary).

## Tool routing

Use `manage_commerce_context_attributes` with `list_attributes` to inspect existing schemas. Use `query_objects` to check existing products, plans, and custom fields. Use `manage_commerce_charges` with `help: true` for charge model guidance. Use `manage_custom_fields` to inspect and create custom field definitions. Use `Read` / `Bash` to inspect CSV/spreadsheet contents when a file path or attachment is provided. Use `mcp__zuora-mcp__ask_zuora` only as a fallback for unresolved product-behavior questions (e.g., "can dynamic pricing coexist with discount charges?") after checking the charge help and references first.

## Workflow

### Step 1: Clarify requirements

Determine the scope:
- **Full catalog setup** — new product + plan + charge with dynamic pricing
- **Add dynamic pricing to existing charge** — new attributes and rate cards on an existing charge
- **Update rate card** — modify prices, add attribute values, add rows
- **CSV / spreadsheet → design** — map an arbitrary price table into the design proposal (see CSV section below)

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
- **Effective dating** — does any price need to change on a future date, or does the price history need to be preserved? (e.g., "US price is $10 today, rises to $12 on 2026-04-01"). If yes, capture the effective start date for each price point. See the effective dating section below.

**Product grouping principle:** If the user describes what looks like multiple products that share the same base name but differ by pricing (e.g., "On-Demand" vs "Reserved" vs "Spot"), consolidate them into ONE product with ONE charge that has MULTIPLE rate cards differentiated by attributes. Don't create separate products for pricing variations.

**Attribute mapping level:** Some attributes can validly map to multiple objects (e.g., "Region" could live on Account, RatePlan, or a usage record). When the mapping level is ambiguous, confirm with the user. Choose based on at what granularity the value changes:
- **Account** — fixed per customer, shared across all subscriptions (e.g., customer region, segment)
- **Subscription** — can differ between subscriptions for the same customer (e.g., commitment type: one sub is "reserved", another "on-demand")
- **RatePlan** — set per rate plan instance within a subscription (e.g., service tier chosen for that specific plan)
- **Usage** — varies per event/record (e.g., resource type, cloud region of the API call). Only available on usage charges.

A single charge can combine attributes at different levels (e.g., `CustomerTier` on Account + `ResourceType` on Usage).

**Effective dating (time-varying pricing):**

Dynamic pricing rate cards support effective dating so a price can change on a future date while the prior price is preserved as history. This is driven by a **reserved attribute named `EffectiveDate`** — it is NOT a business dimension, does NOT map to any object field, and does NOT need a custom field created.

How it works in the catalog:
- `EffectiveDate` is a reserved attribute of type `Datetime`. On each rate card row it takes the `>=` operator only (it marks the row's start / "effective from" instant). Any other operator is rejected.
- The value is an ISO-8601 datetime **with a zone offset**, e.g. `2026-04-01T00:00:00Z` or `2026-04-01T00:00:00-08:00`. A bare local date with no offset is rejected.
- If a rate card row omits `EffectiveDate`, it defaults to "effective from now" (`>= current time`).
- For the **same business-attribute combination**, adding a new row with a later `EffectiveDate` does NOT overwrite the old price. The system automatically closes the previous row to a bounded window ending 1 second before the new start, and the new row becomes the open-ended current price. This builds a price timeline:
  - Old row: US → $10, effective `[original start, 2026-03-31T23:59:59]`
  - New row: US → $12, effective `>= 2026-04-01T00:00:00Z`
- Rows are grouped for timeline purposes by their business attributes only (`EffectiveDate` is excluded from the grouping key). So each unique dimension combination carries its own independent price history.

When to surface effective dating in the design:
- The user wants a scheduled/future price change ("raise EU price to €9 starting next quarter").
- The user wants to backfill or preserve historical prices rather than replace them.
- Two rows in the same request that share the same business attributes AND the same effective date are a duplicate and will be rejected — flag this if the requirements imply it.

If pricing never changes over time, no `EffectiveDate` attribute needs to be shown to the user — the system still records an implicit "effective from now" internally.

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

**Quantity bands vs rate-card attributes:**
- Quantity breakpoints belong in `pricing.tiers` on the charge default and on each rate card row — do **not** model quantity as a business attribute with `between` operators when the charge model is `tiered` or `volume`.
- Business dimensions (region, commitment year, segment, etc.) belong in rate-card `attributes[]`. Each matching row carries its **own full tier table** under `pricing.tiers` (same `Pricing` shape as charge-level default pricing).
- Always confirm with the user: **tiered** (progressive / cumulative across bands) vs **volume** (one price for all units at the landed band). Do not infer the model from price shape alone.

### Step 3b: When input is a CSV or spreadsheet (generic)

Works for **any** tabular price file. Do not hard-code expected headers (e.g. do not require `PID`, `MSP …`, `Tier`, or a specific product family). Infer roles from content, then confirm ambiguous mappings with the user.

1. **Read & profile** (use `Read` / `Bash`): headers, row count, distinct values per column, sample rows. For large files, summarize — do not paste thousands of rows into the design proposal.
2. **Classify every column** into one role (a column has exactly one primary role):

| Role | Meaning | Typical headers (examples only — match by meaning) | Maps to |
|------|---------|------------------------------------------------------|---------|
| Catalog identity | What to sell | product, plan, charge, service, SKU, offer name | Product / Plan / Charge entities |
| Business dimension | Price differentiator that is **not** quantity | region, segment, commitment, term, channel, market | Rate-card `attributes[]` (+ custom field if needed) |
| Quantity / tier bound | Upper (or lower) qty for a band | quantity, qty, up to, units, tier end, band | `pricing.tiers[].upTo` (not a rate-card attribute) |
| Tier label | Optional ordinal label | tier, T1, band # | Documentation only (or ignore if redundant with quantity) |
| Price | Amount | price, list price, amount, rate | `unitAmounts` / `flatAmounts` on the charge or tier |
| Currency | ISO code or name | currency, curr, UOM currency | Plan `activeCurrencies` + amount maps |
| Price format | Per unit vs flat | price format, flat/per unit | Tier `priceFormat` |
| Effective date | When the row starts | effective date, start date, valid from | Rate-card `EffectiveDate` (`>=`, ISO-8601 with offset) |
| Ignore | Row ids, CRM keys, discount ids, notes | id, sf id, external key, comments | Omit from catalog |

3. **Decide catalog grain** from identity columns:
   - Group rows that share the same sellable offer into one Product (+ Plan).
   - Separate **charges** when identity columns describe different billable services/components on that offer.
   - Apply the product grouping principle: values that only change price (region, year, commitment, …) become **attributes + rate cards**, not extra products — unless the user explicitly wants separate catalog items.

4. **Build rate cards vs plain tiers:**
   - **Has ≥1 business dimension** → dynamic pricing: one rate-card row per distinct dimension combination; each row's pricing matches the charge model (single amount **or** full `tiers` table).
   - **No business dimension** (only product/charge + qty + currency + price) → still a valid design, but it is **tiered/volume (or per-unit) catalog pricing**, not attribute-driven rate cards. Say so clearly; do not invent attributes.
   - **Currency alone** is almost never a rate-card attribute — put currencies in `activeCurrencies` and amount maps.

5. **Convert quantity rows into `upTo` chains (generic):**
   - Sort distinct quantity bounds ascending within each (charge × attribute-combination) group.
   - Emit tiers as an **`upTo`-only chain**; omit `from`. Last open-ended tier omits `upTo` (except `tiered_overage`).
   - If the CSV has both `from`/`to` (or start/end) columns, use them only to validate non-overlap; still prefer emitting `upTo`-only in the design/build payload.
   - If the CSV has one row per quantity breakpoint with a single price, that price is the list price for that band — confirm `tiered` vs `volume` before locking the model.
   - Multi-currency: pivot so each tier (or rate-card row) carries a currency→amount map, not separate rate cards per currency.

6. **Fill gaps the CSV never provides** (always ask if missing): charge type, bill cycle / timing, UOM, default fallback pricing, attribute object mapping (Account vs Subscription vs RatePlan vs Usage), whether year/term/advance variants are attributes or separate plans.

7. **Present a column→role mapping table** in the design (or as a prerequisite confirmation) so the user can correct misclassified columns before build. Then produce the normal design proposal, using summarized rate-card/tier tables (representative samples + counts are OK for very large files).

### Step 4: Propose the design

Present a structured proposal. Use the **single-price** Rate Card table for `flat_fee` / `per_unit` / discounts. Use the **tier table per dimension** Rate Card section when `chargeModel` is `tiered` or `volume`. For `tiered_overage`, use that section for the included tiers **and** also capture the separate overage `unitAmounts` (required on that model).

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
- Model: per_unit | tiered | volume | ...
- Type: recurring
- Bill cycle: default_from_customer / monthly / in_advance
- Trigger: contract_effective
- End date condition: subscription_end
- Unit of measure: (required for per_unit / tiered / volume / usage)
- Default pricing: (fallback when no rate card matches — single amount OR default tier table)

### Rate Card (flat_fee / per_unit)
Include an `Effective From` column only when pricing is time-varying. Omit it (or show "now") when all prices are effective immediately.

| Region | CommitmentType | Price (USD) | Effective From |
|--------|---------------|-------------|----------------|
| US | on-demand | $10.00 | now |
| US | reserved | $7.00 | now |
| EU | on-demand | $8.00 | now |
| EU | reserved | $5.50 | now |

### Rate Card (tiered / volume — progressive or volume tiers per dimension)
Each rate-card row is one attribute combination plus a **full** tier table. Show `tierMode` (`tier_mode_tiered` or `tier_mode_volume`). Do not put quantity in the attribute columns.

**Tier boundary rules (critical — wrong boundaries produce invalid or overlapping designs):**
- Prefer chaining tiers with **`upTo` only** (omit `from`). Each row is "quantity up to N"; the last open-ended tier **omits `upTo`**.
- Exception: `tiered_overage` requires **`upTo` on every tier** (no open-ended last tier).
- If you also set `from`, ranges must not overlap (e.g. `upTo: 10` then next `from: 11`, never `from: 10` after `upTo: 10`).
- Do not invent V1 fields (`startingUnit` / `endingUnit` / single `price`) in the design payload notes.

**Default tiers** (no rate card match) — `upTo` chain:

| upTo | Price format | USD |
|------|--------------|-----|
| 100 | per_unit | 10.00 |
| 500 | per_unit | 8.00 |
| (open) | per_unit | 6.00 |

**Rate cards:**

| Region | CommitmentType | Tier table (USD, upTo chain) | Effective From |
|--------|----------------|------------------------------|----------------|
| US | on-demand | ≤100 @ $10; ≤500 @ $8; open @ $6 | now |
| US | reserved | ≤100 @ $7; ≤500 @ $5.50; open @ $4 | now |
| EU | on-demand | ≤100 @ $8; ≤500 @ $6; open @ $5 | now |

For many currencies, either add currency columns inside each tier summary or attach a compact per-row tier appendix — do not flatten quantity bands into separate rate-card rows.

### Pricing Timeline (only if effective dating is used)
Show scheduled price changes as separate rows for the same attribute combination. The system preserves the earlier price as bounded history automatically — you only supply the new "effective from" date.

For tiered/volume, the new row replaces the **entire** prior tier table for that attribute combination at the new effective date (submit full `pricing.tiers`, not a single tier patch).

| Region | CommitmentType | Price / tier table (USD) | Effective From |
|--------|----------------|--------------------------|----------------|
| US | on-demand | $10.00  (or full tier table) | now (implicit) |
| US | on-demand | $12.00  (or full tier table) | 2026-04-01T00:00:00Z |

Resulting effective windows after the system merges:
- US / on-demand → prior pricing for `[now, 2026-03-31T23:59:59]`
- US / on-demand → new pricing for `>= 2026-04-01T00:00:00Z`

### Rate Card Operators
- Region: == (exact match)
- CommitmentType: == (exact match)
- EffectiveDate: >= (reserved attribute; only `>=` is valid — marks the effective-from instant)

### Constraints
- [any edge cases, limitations, or decisions to confirm]
```

### Step 5: Confirm with user

Use `AskUserQuestion` to present the design summary and ask for explicit approval before any build work begins. The question must offer at least these options:

- **Approve — proceed to build** (confirm the design is correct and ready to execute)
- **Revise** (user wants to change something; loop back to update the design)
- **Cancel** (stop without building)

**If the user approves:** tell the user to run `/zuora-dynamic-pricing-build` with the approved design as input to execute it.

**If the user does not approve:** do NOT proceed. Ask what needs to change and re-present an updated design for approval.

Do not call any write/mutating MCP tools (product, plan, charge, custom field creation) in this skill — those belong in the build skill.

## Key constraints to surface in design

- `productRatePlanId` cannot be changed after charge creation
- Tiered/volume pricing: prefer `upTo`-only tier chains; last tier omits `upTo` (unbounded) — EXCEPT `tiered_overage` where ALL tiers require `upTo`. If `from` is set, ranges must not overlap.
- For `tiered` / `volume`, each rate card row uses `pricing.tiers` + `pricing.tierMode` (same shape as charge-level default pricing). Quantity is **not** a rate-card attribute.
- Per-tier amounts use currency maps on the tier (`unitAmounts` / `flatAmounts`) with `priceFormat` `price_format_per_unit` or `price_format_flat_fee` — not a single V1-style `price` field. `priceFormat` defaults to per-unit when omitted.
- Rate card operators: `==`, `>`, `>=`, `<`, `<=`, `between`, `between-inclusive`, `matches` (regex). NOT supported: `!=`
- For `between`/`between-inclusive`, value is an array: `[lower, upper]`
- Attribute types: `String`, `Integer`, `Double` (NOT Decimal), `Boolean`, `Date`, `Datetime`
- Usage charges must NOT include `billCycle.timing`; recurring/one_time SHOULD include it (`in_advance` or `in_arrears`)
- First matching rate card wins; if no rate card matches, default pricing applies
- Mapped fields must exist before attribute creation (standard fields already exist; custom fields must be created first)
- Consolidate pricing variations into rate cards on a single charge — don't create separate products for each price point
- **Effective dating**: `EffectiveDate` is a reserved attribute (type `Datetime`) — do not map it to an object field or create a custom field for it
- `EffectiveDate` accepts only the `>=` operator (marks the effective-from instant); any other operator is rejected
- `EffectiveDate` values must be ISO-8601 with a zone offset (e.g., `2026-04-01T00:00:00Z`); a bare local datetime is rejected
- Omitting `EffectiveDate` on a row means "effective from now"; a future date schedules the change while preserving the prior price as bounded history — you do not supply the end date, the system computes it
- Two rate card rows with the same business attributes AND the same effective date are a duplicate and will be rejected
- For dynamic pricing updates, re-submitting a row whose price equals the price already in effect at its effective date is a no-op and is dropped (does not grow the rate card)
- **CSV inputs:** classify columns by role (identity / dimension / quantity / price / currency / effective date / ignore); never assume fixed header names; currency ≠ rate-card attribute; quantity ≠ rate-card attribute when using `tiered`/`volume`; confirm `tiered` vs `volume`; summarize large files instead of dumping every row
