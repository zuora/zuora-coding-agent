# Commerce Catalog Product Clone — MCP Reference

Reference for cloning **Commerce Catalog products** (and all nested plans/charges) on the **current tenant** via **zuora-mcp**.

## Tool and operation

| Item | Value |
| --- | --- |
| MCP server | `zuora-mcp` |
| Tool | `manage_commerce_products` |
| Operation | `clone_product` |

## Arguments

| Field | Required | Description |
| --- | --- | --- |
| `operation` | Yes | `clone_product` |
| `sourceProductKey` | Yes | Source product id, productNumber, or sku |
| `cloneOptionsJson` | No | Optional behavior overrides (see below) |

Common options: `dryRun`, `namePrefix` (default `copy_`), `includeFeatures`, `includeEntitlements`, `includeDeprecated`, `maxPlansPerProduct`, `maxChargesPerProduct`.

## Execution rule

Always use `mcp__zuora-mcp__manage_commerce_products` with `operation: clone_product`. Never reimplement clone logic locally, and never fall back to `create_product` / `create_plan` when clone fails.

## Workflow

1. **Dry run** — call with `cloneOptionsJson: {"dryRun": true}` to validate the source and get `cloneReport.createPayloadPreview`, plan/charge counts, and `warnings` (e.g. omitted rate cards) without mutating the tenant.
2. **Check scope before executing** — if the preview shows more than a handful of plans/charges, includes deprecated items, or has warnings (e.g. MAP/dynamic charges needing rate cards), use `AskUserQuestion` to confirm with the user before proceeding: show the plan/charge count and any warnings, and ask whether to proceed as-is, narrow the clone (`maxPlansPerProduct`, `maxChargesPerProduct`, `includeDeprecated: false`), or stop. Skip this confirmation only for small, warning-free clones the user has already explicitly approved.
3. **Execute** — same call with `dryRun: false` after approval.
4. **Report the result** — on success, report `cloneReport.clonedProductId`, the cloned name (`copy_<original>`, or the overridden `namePrefix`), and any `cloneReport.warnings`. On failure, surface `success: false`, `message`, and `validationReport` / `cloneReport.validations` verbatim — do not retry with manual create.

## Included in a product clone

- Product header, context filters, custom fields, optional features
- All nested plans and charges (within size limits)
- Standard charge pricing, tax, and accounting fields

## Not supported

`clone_product` clones the whole product aggregate; there is no `clone_plan` on `manage_commerce_plans`. If the user asks to clone only a plan, stop and offer to clone the parent product instead (duplicating its other plans) rather than hand-building plan JSON.

- Cross-tenant clone (same tenant only)
- Standalone plan clone (no `clone_plan`)
- Bundle products
- Dynamic pricing rate card tables (omitted; warnings may appear)
- Partial clone when plan/charge limits are exceeded

## Constraints

- Same-tenant only — does not clone catalog from one tenant to another
- Clone naming: `copy_` + source name (override via `namePrefix`)
- Rate cards are never cloned — warn user MAP/dynamic charges may need rate cards reconfigured
- Default limits: 20 plans / 20 total charges (configurable via `maxPlansPerProduct` / `maxChargesPerProduct`)
- Bundles and standalone plan-only clone are unsupported

## Prerequisites

- **DynamicPricing** enabled (**Settings > Billing > Manage Features > Commerce**)
- Product clone enabled for the tenant
- zuora-mcp OAuth configured (`ZUORA_BASE_URL`, `ZUORA_CLIENT_ID`, `ZUORA_CLIENT_SECRET`)
