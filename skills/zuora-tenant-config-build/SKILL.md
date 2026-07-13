---
name: zuora-tenant-config-build
description: Apply a tenant configuration plan to a Zuora tenant using manage_settings
argument-hint: <configuration plan from /zuora-tenant-config-design or direct instructions>
allowed-tools: [Read, Write, Glob, Grep, mcp__zuora-mcp__manage_settings, mcp__zuora-mcp__manage_custom_fields, mcp__zuora-mcp__query_objects, mcp__zuora-mcp__ask_zuora]
---

You are applying Zuora tenant configuration changes directly to the tenant using MCP tools. This skill executes — it does NOT generate code.

## How `manage_settings` works under the hood

All three operations go through the Zuora Settings batch API (`POST /settings/batch-requests`):

| Operation | HTTP method | When to use |
|-----------|-------------|-------------|
| `list_setting_keys` | — | Discover available paths — fall back to this only if a path is not found in `settings-schema.json` |
| `get_settings` | GET | Read current value before any update |
| `update_settings` | PUT | Update an existing setting or collection item |
| `create_settings` | POST | Create a new collection item (e.g., new payment term) |

Key mechanics:
- **`settingValueJson` must always be a JSON object `{...}`, never a bare array `[...]`**. The tool rejects arrays immediately.
- For **per-ID collection updates**, include the item ID in `settingKey` (e.g., `/payment-terms/abc123`), not in the payload body.
- For **full array replace settings** (e.g., `/currencies`), a single PUT replaces the entire collection — include all items, both changed and unchanged.
- For **new collection items** (e.g., a payment term that doesn't exist yet), use `create_settings` with the base collection key (e.g., `/payment-terms`).
- **Payment gateways are an exception** — gateway creation requires provisioning outside this tool; only updates are supported via `update_settings`.

Always check `"success": true` in the response before moving to the next operation.

---

## Input

The user's configuration plan or instructions: $ARGUMENTS

The plan from `/zuora-tenant-config-design` carries values in UI terms (`field_key` + option strings from `settings-fields.json`). Your job is to translate those into API payloads using `settings-field-mappings.json`, then apply them via `manage_settings`.

If no design plan exists and the request involves more than two settings, recommend running `/zuora-tenant-config-design` first.

---

## Step 1: Confirm target tenant

Before loading any references or applying any changes, fetch the tenant profile and confirm with the user:

```
Tool: manage_settings
operation: get_settings
settingKey: /entity-profile-info
```

Present the result clearly and ask for explicit confirmation:

> **Target tenant:**
> - Name: `<tenantName>`
> - ID: `<tenantId>`
> - Environment: `<bannerLabel>` (`<bannerColor>`)
> - Status: `<status>`
>
> Is this the correct tenant? Please confirm before I apply any changes.

Do not proceed until the user confirms. If the tenant looks wrong (e.g., production when sandbox was expected), stop and ask the user to check their MCP credentials (`ZUORA_BASE_URL`, `ZUORA_CLIENT_ID`, `ZUORA_CLIENT_SECRET`).

---

## Step 2: Load reference files

Read these in parallel:
- `${CLAUDE_PLUGIN_ROOT}/references/settings-field-mappings.json` — for each `group_key` → `field_key`: the API field name (`api_field`), value type, and `value_map` (UI option string → API value). This is your primary translation dictionary.
- `${CLAUDE_PLUGIN_ROOT}/references/settings-schema.json` — API schema per path: field types, enum values, required fields, min/max. Use to validate payloads before sending.
- `${CLAUDE_PLUGIN_ROOT}/references/tenant-config-settings.md` — collection patterns (SINGLETON / ITEM-BY-ID / FULL ARRAY REPLACE) and read-only fields.

---

## Step 3: Retrieve before every update

For each setting key you will modify, call `get_settings` first — even when the plan already includes a payload:

- You need current item IDs to construct per-ID update keys (e.g., `/payment-terms/abc123`).
- For full array replace settings you need the complete current item list to avoid unintentional deletions.
- You need the live field structure to avoid sending stale or conflicting values.

```
Tool: manage_settings
operation: get_settings
settingKey: /billing-rules
```

Run independent retrieves in parallel.

---

## Step 4: Translate plan values → API payload

For each field in the plan, first check `settings-fields.json`:
- If the field has `"ui_only": true`, **skip it entirely** — it cannot be set via the API. Record it in the Step 9 report under "Requires manual setup in Zuora UI" with the intended value and a Zuora UI navigation path.

For all other fields, use `settings-field-mappings.json` to construct the API payload:

1. Look up `group_key` → `fields` → `field_key` entry in the mappings file.
2. Get `api_field` — the camelCase API field name to use in the payload.
   - **If the `field_key` is not found in `settings-field-mappings.json`**: look up the setting path in `settings-schema.json` to find the correct API field name. Use only field names that appear explicitly in the schema.
   - **Never invent or guess an API field name from training knowledge.** If the field cannot be found in either `settings-field-mappings.json` or `settings-schema.json`, skip it and flag it in the report as unresolved.
3. Get `value_map` — look up the UI option string to get the API value.
   - If the option string matches a key in `value_map`, use the mapped value exactly.
   - If there is no `value_map` (plain string/integer fields), use the value directly after any type coercion (e.g., `"30"` → `30` for integer fields).
   - If the option string is not in `value_map` but is a clear substring match of a key, use that match. If genuinely ambiguous, use the `default` value from the mapping and flag a warning in the report.
4. Validate the resulting API value against `settings-schema.json` — confirm it matches the `enum` list if one exists, and satisfies `min`/`max` for integers. If the value is not valid per the schema, do not send it — flag it in the report as unresolved.

Example translation:
```
Plan:  enable_customer_hierarchy = "Yes"
Mapping: api_field="customerHierarchy", value_map={"Yes": true, "No": false}
Schema confirms: customerHierarchy is boolean ✓
Payload field: "customerHierarchy": true

Plan:  available_to_credit_validation_for_credit_memos = "Header-level only"
Mapping: api_field="availableToCreditValidationLevel", value_map={"Header-level only": "HeaderLevel", "Line-level": "HeaderAndItemLevel"}
Schema confirms: availableToCreditValidationLevel is string ✓
Payload field: "availableToCreditValidationLevel": "HeaderLevel"
```

Do this translation for all fields in the plan before making any API calls. Any field that could not be resolved must be listed in the Step 9 report under "Unresolved fields" — do not silently drop them.

---

## Step 5: Apply SINGLETON settings

Send only the fields you want to change. Omit read-only fields. PUT is a partial update for singletons — fields not included in the payload are preserved.

```
Tool: manage_settings
operation: update_settings
settingKey: /billing-rules
settingValueJson: {"availableToCreditValidationLevel": "HeaderLevel", "catchUpBillRun": true}
```

---

## Step 6: Apply COLLECTION settings

### Per-ID update — existing items (e.g., `/payment-terms`, `/payment-gateways`)

From the retrieve response, find the item's `id`. Use it in the `settingKey`:

```
Tool: manage_settings
operation: update_settings
settingKey: /payment-terms/abc123
settingValueJson: {"name": "Net 30", "isActive": true, "isDefault": true, "intervalNumber": 30, "type": "NetPaymentTerm"}
```

### Create — new items (e.g., a payment term that doesn't exist yet)

Use `create_settings` with the base collection key:

```
Tool: manage_settings
operation: create_settings
settingKey: /payment-terms
settingValueJson: {"name": "Net 60", "isActive": true, "isDefault": false, "intervalNumber": 60, "type": "NetPaymentTerm"}
```

**Payment gateways are the exception** — gateway creation requires provisioning outside this tool. If the plan calls for a new gateway, mark it as a manual step.

### Full array replace — e.g., `/currencies`

Retrieve the full current list first. PUT back ALL items (modified + unchanged) as an object wrapping the array. Omitting an existing item from the PUT may deactivate it.

```
Tool: manage_settings
operation: update_settings
settingKey: /currencies
settingValueJson: {
  "items": [
    {"currencyCode": "USD", "active": true, "default": true, "roundingMode": "HalfUp", "roundingIncrement": 0.01, "rate": 1.0},
    {"currencyCode": "EUR", "active": true, "default": false, "roundingMode": "HalfUp", "roundingIncrement": 0.01, "rate": 0.92}
  ]
}
```

The outer `{"items": [...]}` wrapper is required — a bare array will be rejected.

---

## Step 7: Apply custom fields (if in scope)

Custom fields are managed by `manage_custom_fields`, not `manage_settings`.

**List existing before creating:**
```
Tool: manage_custom_fields
operation: list_custom_fields
objectType: Account
```

**Add only if it doesn't already exist:**
```
Tool: manage_custom_fields
operation: add_custom_field
objectType: Account
fieldName: Region__c
label: Region
fieldType: string
```

---

## Step 8: Verify changes

After all updates, retrieve each modified setting key and confirm values match the desired state.

```
Tool: manage_settings
operation: get_settings
settingKey: /billing-rules
```

Report the verified state for each setting. Flag any discrepancies.

---

## Step 9: Report outcome

```
## Configuration Applied

### Successful
- /billing-rules: availableToCreditValidationLevel=HeaderLevel, catchUpBillRun=true ✓
- /payment-terms/abc123: Net 30 updated ✓
- /payment-terms (new): Net 60 created ✓

### Requires manual setup in Zuora UI
These settings cannot be applied via the API — please configure them directly in Zuora:
- **Time Zone:** Pacific Time → Settings > Company Profile > Tenant Profile
- **<field_name>:** <value> → <Zuora UI navigation path>

### Other manual steps
- New payment gateway — must be provisioned outside this tool, then updated via manage_settings

### Unresolved fields (not sent)
- <field_name>: could not find API field name in settings-field-mappings.json or settings-schema.json — verify the field key and retry
- <field_name>: value "<value>" is not valid per settings-schema.json enum — expected one of [...]

### Errors
- <any failure with the error message from the response and suggested resolution>
```

---

## Critical constraints

- **`settingValueJson` is always a JSON object `{...}`** — never a bare array. Wrap array-valued payloads in an object (e.g., `{"items": [...]}`).
- **Per-ID updates need the ID in `settingKey`** (e.g., `/payment-terms/abc123`), not in the payload.
- **New items use `create_settings`; existing items use `update_settings`.** Sending a create to an existing item (or an update without an ID) will fail or target the wrong resource.
- **Never omit items from full array replace payloads** — retrieve first, include all existing items in the PUT.
- **UI-only fields** — any field with `"ui_only": true` in `settings-fields.json` must be skipped; it will fail if sent to the API. These are surfaced in the report under "Requires manual setup in Zuora UI".
- **Security policy integer fields**: `enforcePasswordHistory` accepts only `0`, `4`, `7`; `passwordExpiration` only `0`, `30`, `60`, `90`; `minimumPasswordLength` only `7`, `8`, `10`, `12`. Round to the nearest accepted value and confirm with the user before sending.
- **Document prefixes**: changing prefixes or start numbers after billing documents have been issued may cause numbering conflicts. Warn the user before applying.
- **Default currency**: exactly one currency item must have `"default": true`. Validate before sending the full array.

---

## Tool routing

- `manage_settings` — `get_settings` to read, `update_settings` (PUT) to modify, `create_settings` (POST) to create new collection items.
- `manage_custom_fields` — create or list custom fields only.
- `query_objects` — look up live tenant data or IDs when not returned by retrieve.
- `ask_zuora` — only for an unresolved product-behaviour question after the reference and retrieve results have been checked. Name the exact question.
