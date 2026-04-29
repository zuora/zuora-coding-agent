# Zuora API Integration Patterns

## Pattern: Product catalog setup

Set up the billing catalog in this order:
1. **Create Product** — the top-level container
2. **Create Product Rate Plan** — pricing package within a product
3. **Create Product Rate Plan Charge** — individual charge items within a rate plan

Each level requires the parent's ID. Charges support 16 models:
- Recurring: Flat Fee, Per Unit, Tiered, Volume, Discount Percentage, Discount Fixed Amount, Delivery
- One-Time: Flat Fee, Per Unit, Tiered, Volume
- Usage: Per Unit, Tiered, Volume, Overage, Tiered With Overage, High Watermark, Multi-Attribute

**Tiered vs Volume pricing:**
- Tiered: each tier charged separately (first 10 at $10, next 15 at $8 = $220)
- Volume: all units charged at the tier reached (25 units all at $8 = $200)

## Pattern: Subscription lifecycle

The standard lifecycle via the Order API:

1. **Create subscription** — `create_subscriptions` with order date, account, and rate plans
2. **Amend subscription** — add/remove/update rate plans via order actions
3. **Renew subscription** — `renew_subscriptions` to extend term
4. **Cancel subscription** — `cancel_subscriptions` with cancellation policy

Key decisions at creation:
- **Term type**: TERMED (fixed duration) vs EVERGREEN (month-to-month)
- **Auto-renew**: controls automatic renewal at term end
- **Renewal setting**: `RENEW_WITH_SPECIFIC_TERM` or `RENEW_TO_EVERGREEN`

New account can be created inline with the subscription — requires `name`, `currency`, and `billToContact` (firstName, lastName, workEmail, address).

## Pattern: Billing run

Preview before generating:
1. **Billing preview** — `manage_billing_previews` with `create` operation to project charges
2. **Poll for completion** — preview runs are asynchronous
3. **Download results** — CSV output with projected billing items
4. **Generate invoices** — run billing when ready
5. **Collect payment** — optionally collect immediately via `processingOptions`

Processing options at subscription creation:
- `runBilling: true` — generate invoice immediately
- `collectPayment: false` — do not auto-collect (default safe choice)

## Pattern: Object query

Use `query_objects` for flexible data retrieval:
- **Filter operators**: EQ, NE, LT, GT, LE, GE, SW (starts with), IN
- **Filter format**: `["status.EQ:Active", "name.SW:Test"]`
- **Expand**: include related objects in response
- **Sort**: order results by fields
- **Fields**: select specific fields to reduce payload size
- **Pagination**: cursor-based with pageSize (max 99)

Common query patterns:
- Find active subscriptions: `objectType: "Subscription", filter: ["status.EQ:Active"]`
- Find invoices for account: `objectType: "Invoice", filter: ["accountId.EQ:<id>"]`
- Get account details: `get_account_summary` for a comprehensive view including recent memos

## Pattern: Webhook/callout receiver

For receiving Zuora event notifications:
1. Implement an HTTPS endpoint that accepts POST requests
2. Validate the request signature
3. Parse the notification payload (event type + object data)
4. Process asynchronously — return 200 quickly, handle logic in background
5. Implement idempotency — Zuora may retry notifications

## Pattern: Report execution

1. **Find report** — `manage_reports` with `search_reports` or `list_reports`
2. **Run report** — `run_reports` with report ID and optional filters
3. **Auto-poll** — the tool polls until completion (up to 10 minutes)
4. **Export data** — `manage_reports` with `export_report` for CSV download

For Revenue (RevPro) reports, use `manage_revenue_reports` with a similar flow: list → get filters → run → poll → download.

## Pattern: Billing document management

For invoices, credit memos, and debit memos:
1. **Generate PDF** — `manage_billing_documents` with `generate_pdf` operation
2. **List files** — check available PDFs with `list_files`
3. **Download** — retrieve specific PDF with `download`
4. **Email** — send document to recipients with `email` operation

PDF generation for memos is asynchronous — poll for completion before downloading.

## Anti-patterns to avoid

- **N+1 queries**: Don't query objects one-by-one; use filters and batch queries
- **Polling without limits**: Always set max attempts for async operations
- **Hardcoded IDs**: Product, rate plan, and charge IDs differ between environments
- **Missing error handling**: Always handle 4xx/5xx responses
- **Ignoring pagination**: Large result sets will be truncated without cursor handling
- **Guessing field names**: Always verify against actual model details from the SDK
