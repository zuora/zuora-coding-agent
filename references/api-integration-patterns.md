# Zuora API Integration Patterns

## Pattern: Product catalog setup

Zuora offers two catalog systems. Confirm with the customer which they are using:

### Commerce Catalog (dynamic pricing, REST-only)

Uses `/commerce/` endpoints. Supports dynamic pricing via context attributes.

1. **Create Product** — POST `/commerce/products`
2. **Create Plan** — POST `/commerce/plans` (requires productKey)
3. **Create Charge** — POST `/commerce/charges` (requires productRatePlanId)
4. **Query Charge with pricing context** — POST `/commerce/charges/query` (evaluates dynamic pricing)
5. **Update tier pricing** — PUT `/commerce/tiers`

### Classic Catalog (REST + SDK)

Uses `/v1/object/` endpoints or the Zuora SDK.

1. **Create Product** — POST `/v1/object/product` or SDK `ProductsApi.createProduct()`
2. **Create Product Rate Plan** — POST `/v1/object/product-rate-plan` (requires product ID)
3. **Create Product Rate Plan Charge** — POST `/v1/object/product-rate-plan-charge` (requires rate plan ID)

Each level requires the parent's ID. Charges support 16 models:
- Recurring: Flat Fee, Per Unit, Tiered, Volume, Discount Percentage, Discount Fixed Amount, Delivery
- One-Time: Flat Fee, Per Unit, Tiered, Volume
- Usage: Per Unit, Tiered, Volume, Overage, Tiered With Overage, High Watermark, Multi-Attribute

**Tiered vs Volume pricing:**
- Tiered: each tier charged separately (first 10 at $10, next 15 at $8 = $220)
- Volume: all units charged at the tier reached (25 units all at $8 = $200)

## Pattern: Subscription lifecycle (Order API)

The standard lifecycle via the Order API — all operations use POST `/v1/orders`:

1. **Create subscription** — `type: "CreateSubscription"` order action with rate plans, terms, account
2. **Amend subscription** — `type: "UpdateProduct"` / `"AddProduct"` / `"RemoveProduct"` order actions
3. **Renew subscription** — `type: "RenewSubscription"` order action
4. **Cancel subscription** — `type: "CancelSubscription"` order action with cancellation policy

Key decisions at creation:
- **Term type**: TERMED (fixed duration) vs EVERGREEN (month-to-month)
- **Auto-renew**: controls automatic renewal at term end
- **Renewal setting**: `RENEW_WITH_SPECIFIC_TERM` or `RENEW_TO_EVERGREEN`

New account can be created inline with the subscription — requires `name`, `currency`, and `billToContact` (firstName, lastName, workEmail, address).

## Pattern: Billing preview

Preview before generating:
1. **Create billing preview** — POST `/v1/operations/billing-preview` with target date and account
2. **Poll for completion** — GET `/v1/operations/billing-preview/{id}` (async)
3. **Download results** — CSV output with projected billing items

Processing options at subscription creation (in the order request):
- `runBilling: true` — generate invoice immediately
- `collectPayment: false` — do not auto-collect (default safe choice)

## Pattern: Object query (REST)

GET `/object-query/{objectType}` with query parameters:
- **Filter operators**: EQ, NE, LT, GT, LE, GE, SW (starts with), IN
- **Filter format**: `filter[]` params (e.g., `filter[]=status.EQ:Active&filter[]=name.SW:Test`)
- **Expand**: include related objects via `expand[]` params
- **Sort**: `sort[]` params (e.g., `sort[]=createdDate.DESC`)
- **Fields**: `fields[]` to select specific fields and reduce payload size
- **Pagination**: cursor-based with `pageSize` (max 99)

Common patterns:
- Find active subscriptions: GET `/object-query/subscriptions?filter[]=status.EQ:Active`
- Find invoices for account: GET `/object-query/invoices?filter[]=accountId.EQ:{id}`
- Get account summary: GET `/v1/accounts/{id}/summary` for a comprehensive view

## Pattern: Data Query (bulk export)

For large data exports, use the async Data Query API (Trino SQL):
1. **Submit** — POST `/query/jobs` with SQL statement (`SELECT ... FROM ...`)
2. **Poll** — GET `/query/jobs/{jobId}` until status is `completed`
3. **Download** — retrieve file URL from completed job response

Supports CSV, JSON, TSV output. Queries run against the data warehouse.

## Pattern: GraphQL Object Query

POST to the GraphQL endpoint for flexible real-time queries:
- Introspect available types and fields
- Use plural entry points (e.g., `accounts`, `subscriptions`, not singular)
- Filter, sort, and paginate within the query
- Max 1000 records per query

## Pattern: Billing reports

Pre-built reports in the Zuora reporting system:
1. **Find report** — GET `/api/rest/v1/reports/search?query={name}`
2. **Run report** — POST `/api/rest/v1/reports/{reportId}/reportrun`
3. **Poll** — GET `/api/rest/v1/reportruns/{reportRunId}` until completed
4. **Export** — GET `/api/rest/v1/reportruns/{reportRunId}/export` for CSV download

For Revenue (RevPro) reports, similar flow: list available reports → run → poll → download.

## Pattern: Webhook/callout receiver

For receiving Zuora event notifications:
1. Implement an HTTPS endpoint that accepts POST requests
2. Validate the request signature
3. Parse the notification payload (event type + object data)
4. Process asynchronously — return 200 quickly, handle logic in background
5. Implement idempotency — Zuora may retry notifications

## Pattern: Billing document management

For invoices, credit memos, and debit memos:
1. **Generate PDF** — POST `/v1/invoices/{id}/pdfs` (or credit-memos/debit-memos equivalent)
2. **List files** — GET `/v1/invoices/{id}/files`
3. **Download** — GET the file URL from the files list response
4. **Email** — POST `/v1/invoices/{id}/emails` to send to recipients

PDF generation for memos is asynchronous — poll for completion before downloading.

## Pattern: SDK client setup

All Zuora SDKs follow this structure:

```
// Initialize client with OAuth credentials
client = ZuoraClient(clientId, clientSecret, baseUrl)

// Access API groups
client.ordersApi().createOrder(request)
client.accountsApi().getAccount(accountId)
client.subscriptionsApi().getSubscription(key)
```

Key SDK conventions:
- Use fluent builders for request objects (Java/C#)
- Use keyword arguments (Python)
- Use property assignment (Node.js)
- Always call `.execute()` at the end (Java)

## Anti-patterns to avoid

- **N+1 queries**: Don't query objects one-by-one; use filters and batch queries
- **Polling without limits**: Always set max attempts for async operations
- **Hardcoded IDs**: Product, rate plan, and charge IDs differ between environments
- **Missing error handling**: Always handle 4xx/5xx responses
- **Ignoring pagination**: Large result sets will be truncated without cursor handling
- **Guessing field names**: Always verify against actual model details from the SDK
- **Missing Zuora-Version header**: Always pin to a known API version
