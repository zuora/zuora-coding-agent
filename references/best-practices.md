# Zuora Integration Best Practices

## Authentication

- Use OAuth 2.0 client credentials grant (`/oauth/token` with `grant_type=client_credentials`)
- Cache access tokens and refresh before expiry — do not request a new token on every call
- Never hardcode credentials in source code; use environment variables
- Required headers: `Authorization: Bearer <token>`, `Content-Type: application/json`
- Always include `Zuora-Version` header pinned to a known version (e.g., `2025-08-12`)

## Error handling

- Retry with exponential backoff for transient errors (HTTP 429, 500, 502, 503, 504)
- Respect `Retry-After` header on 429 responses
- Log Zuora correlation IDs from response headers for debugging
- Treat `STOP_AND_CONFIRM` responses as permanent errors — do not retry automatically; these require user action
- Distinguish between validation errors (fix input) and server errors (retry or escalate)

## Pagination

- Always use cursor-based pagination for list operations
- Handle empty result pages gracefully
- Use `pageSize` parameter (max 99 for object queries)
- Continue fetching until no `nextPage` cursor is returned

## Idempotency

- Use `Idempotency-Key` header for create operations to prevent duplicates
- Generate unique keys per logical operation (UUID recommended)
- Same key with same payload = safe retry; same key with different payload = rejected

## Rate limiting

- Implement client-side throttling before hitting limits
- Monitor 429 responses and back off accordingly
- Batch operations where possible to reduce call count
- Use billing preview for projections instead of multiple individual queries

## Date handling

- All dates must be in `YYYY-MM-DD` format
- Be aware of timezone implications — Zuora processes dates relative to tenant timezone
- Use `contractEffectiveDate`, `serviceActivationDate`, `customerAcceptanceDate` appropriately

## Environment management

- Sandbox URLs: `rest.apisandbox.zuora.com` (Cloud 2), `rest.sandbox.na.zuora.com` (Cloud 1), `rest.sandbox.eu.zuora.com` (EU)
- Central sandbox: `rest.test.zuora.com` (US), `rest.test.eu.zuora.com` (EU)
- Production: `rest.zuora.com` (US Cloud 2), `rest.eu.zuora.com` (EU)
- Always test in sandbox before production
- Use environment variables for base URL to switch between environments

## SDK usage

- Use the official Zuora SDK for your language (Java, Python, Node.js, C#)
- Access APIs via `ZuoraClient.{apiClass}().{apiMethod}` pattern
- Use fluent builders for request objects — do not use raw setter methods
- Always fetch actual enum values via `get_model_details` — never guess enum strings
- For discriminated types (Java/C#): instantiate specific subtype, then wrap in base request class
- For queries: use the Object Query API unless a specific API is needed

## Zuora-Version header

- Always specify this header to ensure consistent API behavior
- Pin to a known version and upgrade deliberately
- Different versions may change response shapes or field availability

## Custom fields

- Custom field names end with `__c` (double underscore + c)
- Custom field names are **case-sensitive** — the casing used when the field was created must be preserved exactly (e.g., `MyRegion__c` ≠ `myregion__c`)
- **Never guess or lowercase custom field names.** Always resolve them from the live tenant via `query_objects` with `help=fields` before generating any code that references them
- Pass custom fields as top-level properties on the request object (same level as standard fields) — not inside a nested `customFields` wrapper, unless the specific API requires one
- Validate custom field names exist in the tenant before using them
