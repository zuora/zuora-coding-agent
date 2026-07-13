---
name: zuora-tenant-config-design
description: Infer Zuora tenant settings from business documents, URLs, or descriptions — then produce a reviewed configuration change plan
argument-hint: <documents, URLs, or description of your billing setup>
allowed-tools: [Read, Write, Glob, Grep, WebFetch, mcp__zuora-mcp__manage_settings, mcp__zuora-mcp__manage_custom_fields, mcp__zuora-mcp__query_objects, mcp__zuora-mcp__ask_zuora]
---

You are helping a user configure a Zuora tenant. They may not know Zuora at all. Your job is to understand their business billing setup from whatever inputs they provide — documents, URLs, plain descriptions, or direct instructions — translate those into Zuora settings, and produce a reviewed plan ready for `/zuora-tenant-config-build`.

## Input

What the user has provided: $ARGUMENTS

---

## Step 0: Determine input mode

Read `$ARGUMENTS` and classify into one of two paths:

### Path A — Direct / already-specific
The input is already specific Zuora field names and values (e.g., "set `availableToCreditValidationLevel` to `HeaderLevel`, add Net 30 and Net 60 payment terms"). No inference needed. Skip to **Step 2**.

### Path B — Business artifacts or vague description
The input is one or more of:
- Uploaded or referenced documents (Excel, PDF, Word)
- URLs (company website, pricing page, terms & conditions)
- Plain-language business descriptions ("we bill monthly, customers pay within 30 days, we sell in USD and EUR")
- A mix of the above
- Empty or minimal — the user doesn't know where to start

If `$ARGUMENTS` is empty or unclear, ask the user a single open-ended question before proceeding:

> To configure your Zuora tenant, I need to understand how your business works. Please share any of the following:
> - Your company's pricing page or website URL
> - Documents describing your billing terms, payment policies, or pricing structure (upload or paste content)
> - A plain description: how do you charge customers, in what currencies, on what schedule, with what payment terms?
>
> You don't need to know Zuora — just describe how your business bills.

Wait for the user's response, then continue with **Step 1**.

---

## Step 1: Collect and read all source materials

Load reference files and all user-provided sources in parallel.

**Always read:**
- `${CLAUDE_PLUGIN_ROOT}/references/settings-fields.json` — all configurable fields grouped by `group_key`. Each group has `api_paths` (the setting API paths to call for `get_settings`), `field_name` (human-readable label), `field_key`, `data_type`, and `options` (exact UI-facing option strings). This is your source of truth throughout the design skill.
- `${CLAUDE_PLUGIN_ROOT}/references/tenant-config-settings.md` — collection patterns (SINGLETON / ITEM-BY-ID / FULL ARRAY REPLACE) and read-only field notes.

**For each URL the user provided**, fetch the page content:
```
Tool: WebFetch
url: <user-provided URL>
```

**For each uploaded or referenced document**, read it via the Read tool or use the content the user has pasted.

Collect all extracted information into a working set of business facts before proceeding.

---

## Step 2: Infer (or accept) desired settings

### Path A — Direct input
The user has already specified Zuora fields and values. Accept them as-is. Note any field names or enum values you need to verify against the reference, and correct any that don't match.

### Path B — Inference from business artifacts

Run two parallel inference passes over the collected business facts:

---

#### Pass 1 — Standard settings

Translate the business facts into Zuora settings using `settings-fields.json` as the field catalog. Skip the three custom field groups (`z_billing.custom_fields_billing_objects_`, `z_payments.custom_fields_payment_objects_`, `z_finance.custom_fields_finance_objects_`) — those are handled in Pass 2.

**How to use settings-fields.json for inference:**
- Each group has `fields[]` with `field_key`, `field_name` (human-readable label), and `options` (the exact UI option strings).
- Match business facts to `group_key` + `field_key` entries. The `field_name` and `options` are what the user will see in the review step — always use these, never API field names or API enum values.
- For each inferred field, pick the closest matching option string from `options`. This is the value that flows into the plan and the review.

For each inferred setting record:

| Business fact | group_key | field_key | field_name | Inferred option value | Confidence | Source |
|---------------|-----------|-----------|------------|-----------------------|------------|--------|
| "payment due in 30 days" | `z_billing.customize_payment_terms` | `interval_number` | Interval Number | `30` | High | pricing page |
| "header-level credit validation" | `z_billing.billing_rules` | `available_to_credit_validation_for_credit_memos` | Available to Credit Validation for Credit Memos | `Header-level only` | High | policy doc |
| "bill monthly in advance" | `z_billing.billing_rules` | `invoice_recurring_charges_in_advance_or_arrears_` | Invoice Recurring Charges in Advance or Arrears | `Advanced` | Medium | description |

**Common inference patterns:**
- "Payment due within N days" → `z_billing.customize_payment_terms`, `interval_number = N`, `type = NetPaymentTerm`
- "Auto-renew subscriptions" → `z_billing.define_default_subscription_and_order_settings`, `default_subscriptions_to_auto_renew_ = Yes`
- "Multiple currencies" → `z_billing.customize_currencies`, one entry per currency with `active = True`; primary as `default = True`
- "Customer hierarchy / parent-child accounts" → `z_billing.billing_rules`, `enable_customer_hierarchy = Yes`
- "Invoice prefix / document numbering" → `z_billing.define_document_sequence_sets`
- "Revenue recognition" → `z_finance.accounting_rules`
- "Session timeout / password policy" → `tenant_admin.security_policies`

---

#### Pass 2 — Custom fields discovery

Scan the business artifacts for data points that have **no native Zuora representation**. For each candidate:

**Native check (required before inferring):** Ask — "Does Zuora already support this natively?" Native support includes standard object fields, charge models, Units of Measure, billing rules, payment terms, out-of-the-box subscription/RPC behaviors (expiry, rollover, proration), and any other built-in Zuora feature. If the need is covered natively, **do not** infer a custom field. Only infer when the data has no native Zuora representation. Document this check in the reasoning (e.g., "No native Zuora field stores X on object Y").

**What to look for in the source material:**
- Additional data fields needed on accounts, subscriptions, invoices, etc.
- Legacy system fields that need to be migrated or carried over
- External/CRM IDs and integration reference fields
- Business-specific tracking requirements ("track customer segment", "store cost centre")
- Reporting requirements that need additional data points

**How to define each custom field:**

Each custom field is a collection instance with multiple field properties, all sharing the same `instance_name` (e.g., `"CustomerSegment"`). Use the `object_type` options from `settings-fields.json` for the relevant group.

Rules:
- `api_name` must be PascalCase ending in `__c` (e.g., `CustomerSegment__c`)
- Default `field_max_length` to `100` for string fields unless a longer value is implied
- Set `field_filterable` to `true` for ID/reference fields likely used in queries
- For `picklist` type, list the inferred `field_picklist_values` as comma-separated values from the source material
- Assign each custom field to the correct group based on the object type:
  - `z_billing.custom_fields_billing_objects_` — Account, Amendment, Contact, ContactSnapshot, CreditMemo, CreditMemoItem, CreditTaxationItem, DebitMemo, DebitMemoItem, DebitTaxationItem, Feature, Fulfillment, FulfillmentItem, Invoice, InvoiceItem, InvoiceSchedule, InvoiceScheduleItem, TaxationItem, OrderAction, OrderLineItem, Orders, Product, ProductRatePlan, ProductRatePlanCharge, ProductFeature, Subscription, RatePlan, RatePlanCharge, SubscriptionProductFeature, Usage
  - `z_payments.custom_fields_payment_objects_` — Payment, PaymentMethod, PaymentSchedule, PaymentScheduleItem, Refund
  - `z_finance.custom_fields_finance_objects_` — AccountingCode, AccountingPeriod, JournalEntry, JournalEntryItem

For each inferred custom field, record all its properties as a group sharing an `instance_name`:

| Business fact | group_key | instance_name | field_key | Inferred value | Confidence | Source |
|---------------|-----------|---------------|-----------|----------------|------------|--------|
| "track business unit" | `z_billing.custom_fields_billing_objects_` | `BusinessUnit` | `object_type` | `Account` | High | SOW |
| "track business unit" | `z_billing.custom_fields_billing_objects_` | `BusinessUnit` | `api_name` | `BusinessUnit__c` | High | SOW |
| "track business unit" | `z_billing.custom_fields_billing_objects_` | `BusinessUnit` | `field_type` | `picklist` | High | SOW |
| "track business unit" | `z_billing.custom_fields_billing_objects_` | `BusinessUnit` | `field_picklist_values` | `SAWIN,PRINTREACH,BAYMASTER` | Medium | SOW |

Deduplicate by `object_type + api_name` — if the same field appears more than once, keep only the highest-confidence instance.

---

Mark confidence as:
- **High** — explicitly stated in the source
- **Medium** — reasonably inferred from context
- **Low** — assumed from common defaults; user should confirm

**For Low and Medium confidence inferences, ask the user to confirm before proceeding.** Group all questions into one message rather than asking one at a time.

---

## Step 3: Present inferences for review

Before touching any tenant settings, show the user what you've inferred. Use `field_name` from `settings-fields.json` as the label and the inferred option value as the value — never API field names or API enum values. The user should be able to read and correct this without knowing anything about Zuora internals.

Format:

```
## Inferred Configuration — Please Review

Based on [your pricing page / the document you shared / your description], here's what I'll configure:

### Billing
- **Payment Terms:** Net 30 (default), Net 60
  → Source: "payment within 30 days" on pricing page
- **Invoice Recurring Charges in Advance or Arrears:** Advanced
  → Source: pricing page
- **Enable Customer Hierarchy:** Yes
  → Source: ⚠️ assumed — please confirm if you have parent/child account relationships

### Currencies
- **Active Currencies:** USD (default), EUR
  → Source: pricing page

### Security
- **Session Timeout:** 30 minutes
  → Source: ⚠️ assumed default — let me know if you need a different value

### Custom Fields
- **Account — BusinessUnit__c** (picklist: SAWIN, PRINTREACH, BAYMASTER)
  → Source: "track business unit per account" in SOW
- **Account — LegacyAccountId__c** (string, filterable)
  → Source: migration doc references legacy CRM IDs

---
**Questions before I continue:**
1. Do you have parent/child account relationships that need to share billing? (affects Customer Hierarchy setting)
2. Should session timeout be 30 minutes, or a different value?
3. Are there other business unit values beyond SAWIN, PRINTREACH, BAYMASTER?

Please confirm or correct anything above. Once you approve I'll compare against your current tenant settings and build the change plan.
```

Rules for this step:
- Labels are `field_name` from `settings-fields.json` — never `field_key` or API camelCase names
- Values are option strings from `options[]` — never API enum values like `"HeaderLevel"` or `true/false`
- If a field has no `options` (TEXT type), show the value naturally ("30 days", "Net 30")
- Group by section using plain section names (Billing, Payments, Finance, Admin)
- If a field has `"ui_only": true` in `settings-fields.json`, it cannot be set via the API. List it under a separate **"Requires manual setup in Zuora UI"** section with the inferred value and a note directing the user to configure it in the Zuora UI. Do not include it in the automated plan.

Wait for the user's response and incorporate any corrections before continuing.

---

## Step 4: Retrieve current tenant state

Once the user has confirmed the desired settings, retrieve the current values for all in-scope groups. Run independent calls in parallel.

**For standard settings groups** — look up `api_paths` in `settings-fields.json` and call `get_settings` for each path:

```
Tool: manage_settings
operation: get_settings
settingKey: /billing-rules    ← from api_paths of z_billing.billing_rules
```

If a group has multiple `api_paths` (e.g., `z_billing.define_billing_periods` has `/billing-periods`, `/billing-cycle-types`, `/billing-period-starts`, `/billing-list-price-bases`), call `get_settings` for each path.

If a group has an empty `api_paths` array, it cannot be configured via the Settings API — skip it and note it in the plan as not automatable.

**For custom fields groups** (`z_billing.custom_fields_billing_objects_`, `z_payments.custom_fields_payment_objects_`, `z_finance.custom_fields_finance_objects_`) — these have empty `api_paths` and cannot be read via `manage_settings`. Instead, call `manage_custom_fields` for each object type in the plan to check what's already on the tenant:

```
Tool: manage_custom_fields
operation: list_custom_fields
objectType: Account
```

Run one call per distinct `object_type` across all inferred custom fields. Record existing `api_name` values — any field already present must be excluded from the plan (no re-creation).

Notes:
- **COLLECTION settings** (e.g., `/payment-terms`, `/currencies`, `/payment-gateways`): response contains the current full list. Record existing IDs — required for updates.
- **SINGLETON settings**: response contains current field values.

---

## Step 5: Analyse gaps and conflicts

Compare confirmed desired state against current tenant values:

1. **Changes needed** — fields that differ, with current → desired.
2. **No-ops** — settings already at the desired value; exclude from the plan.
3. **Conflicts** — requirements that cannot be met via the Settings API. The only known case is **new payment gateways**, which require provisioning outside this tool (then can be updated via `update_settings`). Explain any limitation.
4. **Read-only fields** — flag anything from the reference marked non-settable; document the manual UI path.
5. **Collection additions vs updates** — for COLLECTION settings, distinguish new items (`create_settings`) from existing items (`update_settings` by ID).

---

## Step 6: Produce the configuration plan

Output a structured plan. Keep field names in the payloads accurate; use plain language in the summary and notes.

```
## Tenant Configuration Plan

### Summary
<One paragraph in plain language describing what will change.>

### In-scope setting keys
- /billing-rules — <n changes>
- /payment-terms — <new: n, update: m>
- ...

### Changes

#### Billing Rules (z_billing.billing_rules)
Changes (field_key → current option → desired option):
- enable_customer_hierarchy: No → **Yes**
- calculate_taxes_using_information_from_customer_account_of: no change (already "Subscription owner")

#### Payment Terms (z_billing.customize_payment_terms)
Create (new):
- name=Net 30, interval_number=30, default=True, active=True, type=NetPaymentTerm
- name=Net 60, interval_number=60, default=False, active=True, type=NetPaymentTerm

Update (existing — deactivate Net 15):
- id=abc123, active=False

#### Currencies (z_billing.customize_currencies)
Current: USD only
Desired: USD (default), EUR (active)
- alphabetic_code=USD, default=True, active=True
- alphabetic_code=EUR, default=False, active=True

#### Custom Fields
Create (new — not already on tenant):
- Account.BusinessUnit__c: picklist [SAWIN, PRINTREACH, BAYMASTER], filterable=false
- Account.LegacyAccountId__c: string, max_length=100, filterable=true

Already exists (no action):
- Account.ExternalId__c — already present on tenant

### Requires manual setup in Zuora UI
These settings were inferred from your inputs but cannot be applied automatically — please configure them directly in Zuora:
- **Time Zone:** Pacific Time → Settings > Company Profile > Tenant Profile
- **<field_name>:** <inferred value> → <Zuora UI navigation path>

### Not in scope / unsupported
- <User requirement that cannot be met via the Settings API — reason>
```

---

## Step 7: Confirm before building

Ask for the user's sign-off. Specifically call out any destructive or hard-to-reverse changes:
- Deactivating a currency that may have existing transactions
- Changing document prefix or start number after billing has started
- Modifying security policies that affect all users immediately

Do not tell the user to proceed until they explicitly confirm.

After confirmation, tell the user:
> Run `/zuora-tenant-config-build` to apply this plan to your tenant.

---

## Tool routing

- `WebFetch` — fetch URLs the user provides (pricing pages, terms, website).
- `Read` — read uploaded or locally referenced documents.
- `manage_settings` — retrieve current tenant state for standard settings groups; never update in this design skill.
- `manage_custom_fields` — list existing custom fields per object type (Step 4) to identify what's already on the tenant; used in Pass 2 inference to avoid re-creating existing fields.
- `query_objects` — look up live tenant data (e.g., existing payment term names, currencies in use).
- `ask_zuora` — only for an unresolved product-behaviour question after the reference and retrieved values have been checked. Name the exact question and sources already checked.
