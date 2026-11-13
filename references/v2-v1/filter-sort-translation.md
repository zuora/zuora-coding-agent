# Filter, sort, expand, and fields translation reference

## 1. Purpose

Agent-facing translation reference for the public Object Query REST `filter[]`, `sort[]`,
`expand[]`, and `<object>.fields[]` parameters across the five resource cards covered by the
v2-to-v1 field maps. For each card this document provides:

- Filter key mappings (v2 parameter key → public OQ field name)
- Sort key mappings (v2 key → public OQ field name, direction rule)
- Expand relation names (v2 relation name → public `expand[]` value)
- Fields namespace rules (`<object>.fields[]` conventions)
- Limitations (what v2 accepted that the public APIs do not support)

Use the anchor links (e.g. `#accounts-get`) in field-map `transform` text to point readers here
rather than reproducing the tables inline.

---

## 2. Public filter and sort grammar

### 2.1 Filter grammar

Format: `filter[]=<field>.<OP>:<value>`

Multiple `filter[]` parameters combine with AND. There is no OR operator across different fields.

| Operator | Meaning | Notes |
|---|---|---|
| EQ | Exact equal | Case-insensitive for string fields |
| NE | Not equal | Case-insensitive for string fields |
| LT | Less than | Numeric and date comparators |
| GT | Greater than | Numeric and date comparators |
| GE | Greater than or equal | Numeric and date comparators |
| LE | Less than or equal | Numeric and date comparators |
| SW | Starts with | Case-insensitive for string fields |
| IN | List of values | `<field>.IN:[value1,value2]`; case-insensitive |

Date format rules:
- Transaction date fields (invoice date, payment date): `YYYY-MM-DD` without quotes.
- Timestamp fields (`updateddate`): ISO 8601 datetime literal, e.g. `updateddate.LT:<YYYY-MM-DDTHH:MM:SSZ>`.
- Null filter: `<field>.EQ:null`.
- URL encoding: space → `%20`; IN list brackets → `%5B`, `%5D`.

Fields can only be filtered if listed under `filter[]` of the specific API operation in the API
reference.

### 2.2 Sort grammar

Format: `sort[]=<field>.asc` or `sort[]=<field>.desc`

v2 sort rules (source-observed):
- One field only. Exactly one `sort[]` value is accepted; two or more raise a 400 error.
- No related-object fields. Field names in `sort[]` are translated with the filter and sort key tables of each card; any key not in a table is passed through unchanged.
- Direction tokens: `asc` → `ASC`, `desc` → `DESC`.

### 2.3 v2 filter operators

The v2 filter grammar supports: `EQ`, `NE`, `GT`, `LT`, `SW`, `IN` (expanded to OR-of-EQ conditions at the OQ layer).

**Differences from the public grammar:**
- `GE` and `LE` operators: the public grammar documents GE and LE; v2's parser accepts
  only `EQ|NE|GT|LT|SW|IN`. Customers who used GE/LE-style comparisons in v2 may need to
  rewrite them using GT/LT or adjust their filter logic.
- `IN` operator: v2 expands IN into a series of EQ conditions combined with OR at the OQ
  GraphQL layer. The public OQ REST `IN` operator is
  documented and should be used directly.
- OR across different fields: neither v2 nor the public grammar supports OR across distinct
  fields. Make two calls and combine in code.

### 2.4 Page size and key naming

- Page size: v2 `page_size` accepts 1 to 99. The public Object Query `pageSize` also accepts 1 to 99 (default 10), so a v2 value carries over unchanged.
- Filter, sort and expand names are case-insensitive (for example `invoicedate` and `invoiceDate` are the same); the tables below show the public names as documented.

**Name rule for `fields[]` (observed on a test tenant):** the root object takes `fields[]` or `<object>.fields[]` where the object name is written without underscores or hyphens (`invoice`, `invoices`, `invoiceitem`, `invoiceitems`, `creditmemo`, `creditmemos`); an expanded relation takes its public expand name (`invoiceitems.fields[]`, `rateplans.fields[]`, `billto.fields[]`). A name the API does not know, such as a v2 name with underscores (`invoice_item.fields[]`, `subscription_plans.fields[]`, `items.fields[]`), is silently ignored and the full record is returned.

---

## 3. Card sections

---

### accounts-get

Card: `accounts.get` (GET /accounts/{account_id})
Object: `account`

#### 3.1.1 Filter keys

`accounts.get` is a get-by-key operation. The public Object Query equivalent is
`/object-query/accounts/{key}`. This operation does **not** accept `filter[]`; the account is
identified by the path key.

#### 3.1.2 Sort keys

Not applicable; `accounts.get` returns a single record and does not accept `sort[]`.

#### 3.1.3 Expand relation names

| v2 expand value | public `expand[]` value | Notes |
|---|---|---|
| `subscriptions` | `subscriptions` | Returns an array; per-parent paging is not controllable via public REST |
| `payment_methods` | `paymentmethods` | Returns an array |
| `payments` | `payments` | Returns an array |
| `billing_documents` | `invoices` | Returns the account's invoices as an array (one of three document kinds) |
| `billing_documents` | `creditmemos` | Returns the account's credit memos as an array (one of three document kinds) |
| `billing_documents` | `debitmemos` | Returns the account's debit memos as an array (one of three document kinds) |
| `bill_to` | `billto` | Returns a single contact object |
| `sold_to` | `soldto` | Returns a single contact object |
| `default_payment_method` | `defaultpaymentmethod` | Returns a single payment method object |
| `usage_records` | `usages` | Returns an array |
| `invoices` | `invoices` | Returns an array |
| `credit_memos` | `creditmemos` | Returns an array |
| `debit_memos` | `debitmemos` | Returns an array |

Nested expansions: v2 accepts paths of up to three segments. The public API documents `subscriptions.rateplans` and `subscriptions.rateplans.rateplancharges` for accounts (`subscription_plans` is `rateplans`, `subscription_items` is `rateplancharges`); other nested paths are not documented.

Names are case-insensitive. Array relations return results without per-parent paging control via public REST; for per-parent paging use Object Query GraphQL (see the graphql-parity reference).

#### 3.1.4 Fields namespace rules

Top-level object fields: use `account.fields[]=<field1>,<field2>` (or `accounts.fields[]`).
Nested expansion fields: use `<relation>.fields[]=<field1>,<field2>` after including the
`expand[]` value, e.g. `expand[]=subscriptions&subscriptions.fields[]=id,state`.

v2 field names in `<object>.fields[]` are mapped through the object metadata to public OQ field
names before the upstream GraphQL fetch is narrowed. The public `<object>.fields[]` projection
narrows only the output; it does not narrow the upstream OQ REST fetch.

Output field order is not preserved.

#### Not supported by the public APIs

- `filter[]` on `accounts.get`: the get-by-key operation identifies the account by the path key; it accepts no `filter[]`.
- `page_size` on `accounts.get`: single-record endpoint; not applicable.

---

### accounts-list

Card: `accounts.list` (GET /accounts)
Object: `account`

#### 3.2.1 Filter keys

| v2 filter key | public OQ field name | Identifier kind |
|---|---|---|
| `id` | `Id` | 32-hex record ID |
| `updated_time` | `UpdatedDate` | ISO timestamp |
| `account_number` | `AccountNumber` | string |
| `batch` | `Batch` | string |
| `balance` | `Balance` | number |
| `bill_cycle_day` | `BillCycleDay` | integer |
| `name` | `Name` | string |
| `parent_account_id` | `ParentId` | 32-hex record ID |
| `status` | `Status` | enum (see 3.2.4) |
| `crm_id` | `CrmId` | string |
| `currency` | `Currency` | string |
| `communication_profile_id` | `CommunicationProfileId` | 32-hex record ID |
| `default_payment_method_id` | `DefaultPaymentMethodId` | 32-hex record ID |
| `invoice_template_id` | `InvoiceTemplateId` | 32-hex record ID |
| `last_invoice_date` | `LastInvoiceDate` | date `YYYY-MM-DD` |
| `bill_to_id` | `BillToId` | 32-hex record ID |
| `sold_to_id` | `SoldToId` | 32-hex record ID |

No enum translation for `status`: the value is passed through unchanged.

#### 3.2.2 Sort keys

Same keys and OQ field names as the filter table above apply. One field only; direction ASC or
DESC. Related-object fields cannot be used in `sort[]`.

#### 3.2.3 Expand relation names

Same as `accounts-get` section 3.1.3.

#### 3.2.4 Fields namespace rules

Same as `accounts-get` section 3.1.4. Use `account.fields[]` or `accounts.fields[]` for the
root object; `<relation>.fields[]` for expanded objects.

#### Not supported by the public APIs

- Multi-field sort: v2 raised a 400 error for more than one `sort[]` value; the public API also
  accepts only one sort field. No GraphQL recipe covers multi-field sort; see GP-none.
- OR across different filter fields: use two calls and combine in code.
- Related-object filter keys (e.g. filtering by a subscription field from the account list):
  not supported by the public filter grammar; use Object Query GraphQL (GP-none for this case).

---

### billing_documents-list

Card: `billing_documents.list` (GET /billing_documents)
Object: `billing_document` (union of invoice, credit memo, debit memo)

#### 3.3.1 Filter keys

The `billing_documents.list` operation uses three parallel OQ REST queries (invoices,
credit-memos, debit-memos). The v2 filter keys are mapped differently per document type:

**Invoice filter and sort keys:**

| v2 filter key | public OQ field name | Notes |
|---|---|---|
| `id` | `Id` | 32-hex record ID |
| `updated_time` | `UpdatedDate` | ISO timestamp |
| `account_id` | `AccountId` | 32-hex record ID |
| `document_date` | `InvoiceDate` | date `YYYY-MM-DD` |
| `billing_document_number` | `InvoiceNumber` | string |
| `state` | `Status` | enum (see below) |
| `remaining_balance` | `Balance` | number |
| `reversed` | `Reversed` | boolean |
| `total` | `Amount` | number |
| `due_date` | `DueDate` | date `YYYY-MM-DD` |

Invoice `state` enum translation (v2 → OQ `Status`):

| v2 state value | OQ Status value |
|---|---|
| `draft` | `Draft` |
| `posted` | `Posted` |
| `open` | `Posted` |
| `canceled` | `Canceled` |
| `failed` | `Error` |

**Credit memo and debit memo filter and sort keys:**

| v2 filter key | public OQ field name | Notes |
|---|---|---|
| `id` | `Id` | 32-hex record ID |
| `updated_time` | `UpdatedDate` | ISO timestamp |
| `account_id` | `AccountId` | 32-hex record ID |
| `document_date` | `MemoDate` | date `YYYY-MM-DD` |
| `billing_document_number` | `MemoNumber` | string |
| `state` | `Status` | enum (see below) |
| `remaining_balance` | `Balance` | number |
| `reversed` | not available | The public credit and debit memo APIs have no such field: remove the filter or sort, or apply it in your code |
| `total` | `TotalAmount` | number |

Memo `state` enum translation (v2 → OQ `Status`):

| v2 state value | OQ Status value |
|---|---|
| `draft` | `Draft` |
| `open` | `Posted` |
| `uncollectible` | `Canceled` |
| `failed` | `Error` |

Apply the invoice keys to step s1 (invoices endpoint) and the memo keys to steps
s2 (credit-memos) and s3 (debit-memos) of the three-step union.

#### 3.3.2 Sort keys

Same keys as the filter tables (the invoice keys for invoices, the memo keys for memos).
One field only; direction ASC or DESC. The same sort is applied to all three OQ queries; results
across three collections are not guaranteed to be globally sorted.

#### 3.3.3 Expand relation names

| v2 expand value | public `expand[]` value | Notes |
|---|---|---|
| `items` | `invoiceitems` | Invoice step: returns the invoice items as an array |
| `items` | `creditmemoitems` | Credit memo step: returns the credit memo items as an array |
| `items` | `debitmemoitems` | Debit memo step: returns the debit memo items as an array |

Names are case-insensitive. Array relations return results without per-parent paging control via public REST; for per-parent paging use Object Query GraphQL (see the graphql-parity reference).

#### 3.3.4 Fields namespace rules

v2 accepts three overlapping fields parameter names:
- `fields[]`: top-level fields parameter (treated as the root billing document object fields)
- `billing_document.fields[]` (or `billing_documents.fields[]`): explicit billing document
  fields
- `billing_document_item.fields[]` (or `billing_document_items.fields[]`): fields for line
  items when `items` is expanded

Use `invoice.fields[]` / `creditmemo.fields[]` / `debitmemo.fields[]` on the respective OQ
REST steps. For expanded items use `invoiceitems.fields[]`, `creditmemoitems.fields[]` or `debitmemoitems.fields[]` (the public expand name of the step).

Output field order is not preserved.

#### Not supported by the public APIs

- Multi-field sort: one sort field per request; global cross-collection sort is not supported.
- OR across different filter fields: use two calls and combine in code.
- Per-parent item paging: array relations return without per-parent paging control via public
  REST; use Object Query GraphQL (GP-1/GP-2 for invoice items).

---

### invoice_items-list

Card: `invoice_items.list` (GET /invoice_items)
Object: `invoice_item`

#### 3.4.1 Filter keys

| v2 filter key | public OQ field name | Notes |
|---|---|---|
| `id` | `Id` | 32-hex record ID |
| `updated_time` | `UpdatedDate` | ISO timestamp |
| `subscription_id` | `SubscriptionId` | 32-hex record ID |
| `subscription_plan_id` | `RatePlanChargeId` | 32-hex record ID (maps to same field as subscription_item_id) |
| `subscription_item_id` | `RatePlanChargeId` | 32-hex record ID |
| `plan_id` | `ProductRatePlanChargeId` | 32-hex record ID (maps to same field as price_id) |
| `price_id` | `ProductRatePlanChargeId` | 32-hex record ID |
| `status` | not available | The public invoice item API has no such field: remove the filter or sort, or apply it in your code |
| `invoice_id` | `InvoiceId` | 32-hex record ID |
| `billing_document_id` | `InvoiceId` | 32-hex record ID (aliases invoice_id) |

The public invoice item list requires a filter (an unfiltered call fails with HTTP 500 "A filter is required"); v2 allowed an unfiltered list. For example, use `filter[]=invoiceid.EQ:<invoice id>`.

#### 3.4.2 Sort keys

Same keys as the invoice item filter table; one field only, direction ASC or DESC.

#### 3.4.3 Expand relation names

| v2 expand value | public `expand[]` value | Notes |
|---|---|---|
| `subscription` | `subscription` | Returns a single subscription object |
| `subscription_item` | `rateplancharge` | Returns a single rate plan charge (the subscription item) |
| `taxation_items` | `taxationitems` | Returns an array of taxation items |
| `invoice` | `invoice` | Returns a single invoice object |
| `line_item` | `orderlineitem` | Returns a single order line item |

Names are case-insensitive. Array relations return results without per-parent paging control via public REST; for per-parent paging use Object Query GraphQL (see the graphql-parity reference).

#### 3.4.4 Fields namespace rules

Use `invoiceitem.fields[]` or `invoiceitems.fields[]` for the root object. Use
`<relation>.fields[]` for expanded objects (e.g. `subscription.fields[]`).

Output field order is not preserved.

#### Not supported by the public APIs

- Multi-field sort: one sort field only.
- OR across different filter fields: use two calls and combine in code.
- Related-object filter keys: not supported by the public filter grammar.
- Per-parent paging on `taxation_items`: GP-none.

---

### invoices-get

Card: `invoices.get` (GET /invoices/{invoice_id})
Object: `invoice`

#### 3.5.1 Filter keys

`invoices.get` is a get-by-key operation. The public Object Query equivalent is
`/object-query/invoices/{key}`. This operation does **not** accept `filter[]`.

Key format: if the key is exactly 32 hexadecimal characters, it is treated as the record ID
(`Id`); otherwise it is treated as the invoice number (`InvoiceNumber`).

#### 3.5.2 Sort keys

Not applicable; `invoices.get` returns a single record and does not accept `sort[]`.

#### 3.5.3 Expand relation names

| v2 expand value | public `expand[]` value | Notes |
|---|---|---|
| `account` | `account` | Returns a single account object |
| `items` | `invoiceitems` | Returns an array of invoice items; nested paging via GP-1 |
| `bill_to` | `billtocontact` | Returns a single contact object (GP-3) |
| `sold_to` | not available | No public REST expand: the invoice REST API only offers a snapshot of the sold-to contact (`soldtocontactsnapshot`); the live contact is available through Object Query GraphQL (GP-3) |

Names are case-insensitive. Array relations return results without per-parent paging control via public REST; for per-parent paging use Object Query GraphQL (see the graphql-parity reference).

**Values of `fields[]`:** a `fields[]` value is a public field name, taken from the `target.field` of the matching response items in the route file (for example `invoiceNumber`, `dueDate`), written in the namespace below. v2 snake_case names (`invoice_number`) are not translated by the server and are silently ignored (the full record is returned), so always use the public names.

#### 3.5.4 Fields namespace rules

Use `invoice.fields[]` or `invoices.fields[]` for the root object. Use `invoiceitems.fields[]` for
expanded invoice items. The public `<object>.fields[]` narrows the output response; v2's
GraphQL path narrows the upstream fetch (GP-7 documents the difference).

Output field order is not preserved.

#### Not supported by the public APIs

- `filter[]` on `invoices.get`: single-record get-by-key; no `filter[]`.
- Per-parent nested item paging: use Object Query GraphQL (GP-1).
- Expansions beyond `account`, `items`, `bill_to`, `sold_to`: no vetted GraphQL recipe (GP-none).
- Field narrowing parity with v2 upstream fetch narrowing: GP-7.

---

### invoices-list

Card: `invoices.list` (GET /invoices)
Object: `invoice`

#### 3.6.1 Filter keys

| v2 filter key | public OQ field name | Notes |
|---|---|---|
| `id` | `Id` | 32-hex record ID |
| `updated_time` | `UpdatedDate` | ISO timestamp |
| `account_id` | `AccountId` | 32-hex record ID |
| `document_date` | `InvoiceDate` | date `YYYY-MM-DD` |
| `billing_document_number` | `InvoiceNumber` | string |
| `state` | `Status` | enum (see below) |
| `remaining_balance` | `Balance` | number |
| `reversed` | `Reversed` | boolean |
| `total` | `Amount` | number |
| `due_date` | `DueDate` | date `YYYY-MM-DD` |

Invoice `state` enum translation (v2 → OQ `Status`):

| v2 state value | OQ Status value |
|---|---|
| `draft` | `Draft` |
| `posted` | `Posted` |
| `open` | `Posted` |
| `canceled` | `Canceled` |
| `failed` | `Error` |

#### 3.6.2 Sort keys

Same keys as the invoice filter table. One field only, direction ASC or DESC. The same keys as
the filter table above apply.

#### 3.6.3 Expand relation names

Same as `invoices-get` section 3.5.3. The `items` expansion with `invoices.list` uses GP-2
for per-parent items paging.

#### 3.6.4 Fields namespace rules

Same as `invoices-get` section 3.5.4. The `page_size` parameter applies to both the root
invoice page and the nested items page when `expand[]=items` is active; this behavior is not
replicable via public OQ REST alone (GP-4).

#### Not supported by the public APIs

- Multi-field sort: one sort field only.
- OR across different filter fields: use two calls and combine in code.
- Per-parent nested item paging: use Object Query GraphQL (GP-2).
- Field narrowing parity with v2 upstream fetch narrowing: GP-7.

---

### subscriptions-get

Card: `subscriptions.get` (GET /subscriptions/{subscription_id})
Object: `subscription`

#### 3.7.1 Filter keys

`subscriptions.get` is a get-by-key operation. The public Object Query equivalent is
`/object-query/subscriptions/{key}`. This operation does **not** accept `filter[]`.

Key format: 32-hex → record ID; otherwise → subscription number (`Name`).

#### 3.7.2 Sort keys

Not applicable; `subscriptions.get` returns a single record and does not accept `sort[]`.

#### 3.7.3 Expand relation names

| v2 expand value | public `expand[]` value | Notes |
|---|---|---|
| `subscription_plans` | `rateplans` | Returns an array of rate plans (subscription plans) |
| `account` | `account` | Returns a single account object |
| `invoice_owner_account` | `invoiceowner` | Returns a single account object |
| `bill_to` | `billtocontact` | Returns a single contact object |
| `sold_to` | `soldtocontact` | Returns a single contact object |
| `invoice_items` | `invoiceitems` | Returns an array of invoice items |
| `prepaid_balance` | not available | Not an expand in the public REST API: prepaid balances are a separate resource (`/object-query/prepaid-balances`, requires the prepaid feature); no vetted GraphQL example |
| `prepaid_balances` | not available | Not an expand in the public REST API: prepaid balances are a separate resource (`/object-query/prepaid-balances`, requires the prepaid feature); no vetted GraphQL example |

Nested expansions: the public API documents `rateplans.rateplancharges`, `rateplans.rateplancharges.rateplanchargetiers` and `rateplans.rateplancharges.discountapplydetails` for subscriptions; the v2 `price` segment has no documented public equivalent.

Names are case-insensitive. Array relations return results without per-parent paging control via public REST; for per-parent paging use Object Query GraphQL (see the graphql-parity reference).

#### 3.7.4 Fields namespace rules

Use `subscription.fields[]` or `subscriptions.fields[]` for the root subscription. Use
`rateplans.fields[]` for expanded rate plans, `account.fields[]` for the expanded account,
and so on.

Output field order is not preserved.

#### Not supported by the public APIs

- `filter[]` on `subscriptions.get`: single-record get-by-key; no `filter[]`.
- Per-parent paging on `subscription_plans`, `invoice_items`: GP-none / GP-1 for invoice items.
- Expansions beyond the table above: no vetted GraphQL recipe (GP-none).

---

### subscriptions-list

Card: `subscriptions.list` (GET /subscriptions)
Object: `subscription`

#### 3.8.1 Filter keys

| v2 filter key | public OQ field name | Notes |
|---|---|---|
| `id` | `Id` | 32-hex record ID |
| `account_id` | `AccountId` | 32-hex record ID |
| `contract_effective` | `ContractEffectiveDate` | date `YYYY-MM-DD` |
| `invoice_owner_account_id` | `InvoiceOwnerId` | 32-hex record ID |
| `updated_time` | `UpdatedDate` | ISO timestamp |
| `subscription_number` | `Name` | string |
| `state` | `Status` | enum (see below) |
| `start_date` | `TermStartDate` | date `YYYY-MM-DD` |
| `latest_version` | `IsLatestVersion` | boolean |
| `version` | `Version` | integer |
| `end_date` | `TermEndDate` | date `YYYY-MM-DD` |

Subscription `state` enum translation (v2 → OQ `Status`):

| v2 state value | OQ Status value |
|---|---|
| `draft` | `Draft` |
| `pending_activation` | `Pending Activation` |
| `pending_acceptance` | `Pending Acceptance` |
| `active` | `Active` |
| `expired` | `Expired` |
| `canceled` | `Cancelled` |
| `paused` | `Suspended` |

#### 3.8.2 Sort keys

Same keys as the subscription filter table. One field only, direction ASC or DESC. The same keys
as the filter table above apply.

#### 3.8.3 Expand relation names

Same as `subscriptions-get` section 3.7.3.

#### 3.8.4 Fields namespace rules

Same as `subscriptions-get` section 3.7.4.

#### Not supported by the public APIs

- Multi-field sort: one sort field only.
- OR across different filter fields: use two calls and combine in code.
- Related-object filter keys: not supported by the public filter grammar.
- Per-parent paging on nested arrays: GP-none.

---

### subscriptions-versions

Card: `subscriptions.versions` (GET /subscriptions/{subscription_id}/versions)
Object: `subscription` (all versions, identified via `subscription_id` path → filter)

#### 3.9.1 Filter keys

Same key mapping table as `subscriptions-list` section 3.8.1. The `subscription_id` path
parameter is translated to `filter[]=id.EQ:<value>` (if 32-hex) or
`filter[]=name.EQ:<value>` (otherwise) before combining with user-supplied filters.

#### 3.9.2 Sort keys

Same keys as the subscription filter table. One field only, direction ASC or DESC.

Default sort when no `sort[]` is supplied: `version.desc`.

#### 3.9.3 Expand relation names

| v2 expand value | public `expand[]` value | Notes |
|---|---|---|
| `subscription_plans` | `rateplans` | Returns an array of rate plans |
| `account` | not available | No public REST expand for the creator account of a version; no vetted GraphQL example |
| `invoice_owner_account` | not available | No public REST expand for the creator invoice owner of a version; no vetted GraphQL example |
| `bill_to` | `billtocontact` | Returns a single contact object |
| `actions` | not available | No public REST expand for order actions of a version; no vetted GraphQL example |

Names are case-insensitive. Array relations return results without per-parent paging control via public REST; for per-parent paging use Object Query GraphQL (see the graphql-parity reference).

#### 3.9.4 Fields namespace rules

Same as `subscriptions-list` section 3.8.4. Use `subscription.fields[]` or
`subscriptions.fields[]` for the root object (the version list returns subscription version
records through the same subscription OQ object).

Output field order is not preserved.

#### Not supported by the public APIs

- Multi-field sort: one sort field only.
- OR across different filter fields: use two calls and combine in code.
- Related-object filter keys: not supported by the public filter grammar.
- Per-parent paging on nested arrays: GP-none.

---

## 4. General limitations (applies to all cards)

| Limitation kind | Description | Guidance |
|---|---|---|
| `grammar_limited` | v2 accepted operators (`EQ`, `NE`, `GT`, `LT`, `SW`, `IN`) that map to the public OQ grammar. The public grammar additionally documents `GE` and `LE`; those were not accepted by v2's parser. | Use the documented public operators directly. |
| `paging_not_controllable` | Array expansion results (nested `subscription_plans`, `invoice_items`, `items`, etc.) have no per-parent paging parameter via public OQ REST. | Use Object Query GraphQL; see GP-1/GP-2 for invoice items, GP-none for others. |
| `differs_from_v2` | The public OQ REST API behavior differs from v2 in documented ways. v2 `fields[]` narrows the upstream GraphQL fetch before sending; public OQ REST `fields[]` narrows the response only (GP-7). | Follow the specific row's guidance; for fetch-narrowing parity see GP-7. |
| `fields_not_available` | The public APIs do not return this value. | See the specific row's guidance for alternatives. |
| `not_supported_public` | The feature (e.g. multi-field sort, OR across distinct fields) is not supported by the public API. | For multi-field sort and OR, see GP-none. |
