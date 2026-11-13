# Object Query GraphQL parity reference

## 1. Purpose and caveat

This document provides vetted guidance for an agent that needs to suggest Object Query GraphQL to customers who are migrating from v2 and need parity that v1 REST or public Object Query REST cannot provide. Each entry (`GP-<n>`) gives a query document, variable bindings, and adaptation notes. Cases with no vetted example are listed explicitly as `GP-none`.

**Caveat (applies to every entry):** Object Query GraphQL is a public, customer-facing API, but it is undocumented — no server SDL, schema, field-type contract, nullability guarantee, cursor lifetime, or ordering guarantee is available or claimed here. All facts are source-observed from the v2 implementation. Nothing in this document is a server contract. Customer implementations must treat this as guidance derived from observed behaviour, not a specification.

Never copy query text, endpoints, or connection vocabulary from this document into field-map rows, mapping hints, or any audit artifact. This document is guidance to an agent, not an audit record.

---

## 2. Transport facts (source-observed)

- **Endpoint:** `POST <your base URL>/object-query/graphql`, where `<your base URL>` is the same host the customer already uses for the REST routes of the same environment (production, sandbox, region); the path is the REST Object Query path `/object-query` plus `/graphql`.
- **Request body:** JSON object with two keys: `query` (the printed GraphQL document string) and `variables` (a JSON object of variable values). The operation name is not sent by the v2 client.
- **Authorization:** same bearer token as all other v2 requests. Customers use their own OAuth bearer token in the same header.
- **Selected headers the v2 client adds (internal only, do not copy):** `Zuora-Realtime-Read: true`, a client-id header, `Zuora-Cache-Enabled: false`, and conditionally `Zuora-Entity-Ids`. Customers send only their own bearer token and their entity scope header.
- **Timeout:** 75 000 ms (source-observed; not a server contract).
- **Redirects:** 0 (source-observed).
- **Response:** `res.data` from the HTTP response — a JSON object with a `data` key and optionally an `errors` key.

Customer implementation rule: check HTTP status first; then reject any non-empty `errors` array even on HTTP 200; then validate the mandatory `data` shape. Never suppress a failure as empty data.

---

## 3. General rules

### 3.1 Id versus record number

A key that is exactly 32 hexadecimal characters selects `field: "Id"`; any other key selects the object's number field (e.g. `InvoiceNumber`, `AccountNumber`). Apply this rule when building the `filter` variable.

### 3.2 `pageSize` literal slots

`pageSize` is a typed integer literal embedded in the query document — it is not a variable. The v2 implementation rewrites the integer slot before sending the query. When adapting these queries, replace the integer literal with the desired value. There is no independent variable for child page size; the same `page_size` value fills both the root and nested list slots when `expand[]` is used (GP-4).

### 3.3 Cursor on root connection only

The `cursor` variable is passed to the root connection only. Nested connections (`invoiceitems`, etc.) do not accept a replay cursor in these vetted queries; nested `pageInfo.endCursor` is returned but never replayed. Do not substitute a nested token into a root cursor or vice versa.

### 3.4 Edge and node shape

All vetted queries follow the pattern:
```
edges {
  node { ... }        # or an alias: item: node { ... }
}
```
`pageInfo { endCursor }` appears on the root connection in list queries (GP-2, GP-5) and on nested connections (GP-1 through GP-4). A null or absent `endCursor` means the page is the last page (source-observed termination signal; not a server contract).

### 3.5 Absence handling

- An absent key in the GraphQL response is not the same as an explicit `null`. Never synthesize a value for an absent key.
- `null` custom-field values are preserved by default (`PRESERVE_NULL_CUSTOM_FIELDS` defaults to `true`; only the literal string `"false"` disables it — that is the rollback path, not the default). Do not coerce null custom-field values to zero unless the customer explicitly enables the rollback path.

---

## 4. GP entries

---

### GP-1: Invoice items under a single invoice (direct)

**When to use:** The customer is calling `invoices.get` (or `invoice_items.list` with a single `invoice_id` filter) and needs the `items` expansion. v1 REST does not support per-parent nested-item paging; Object Query REST `pageSize` applies only to the root invoices list. Use GP-1 when fetching items for exactly one invoice identified by its key.

**Vetted document:**

```graphql
query getInvoice($filter: invoiceFilterInput) {
  invoices(pageSize: 1, filter: $filter) {
    edges {
      node {
        Id
        invoiceitems(pageSize: 10) {
          pageInfo {
            endCursor
          }
          edges {
            item: node {
              customFields { key value type }
              CreatedById
              UpdatedById
              CreatedDate
              Id
              UpdatedDate
              ChargeAmount
              BookingReference
              AppliedToInvoiceItemId
              ProductRatePlanChargeId
              ProcessingType
              DeferredRevenueAccountingCode { GLAccountName }
              Description
              InvoiceId
              SKU
              ChargeName
              PurchaseOrderNumber
              Quantity
              RecognizedRevenueAccountingCode { GLAccountName }
              Balance
              RevenueRecognitionRuleName
              ServiceEndDate
              ServiceStartDate
              AccountReceivableAccountingCode { GLAccountName }
              SubscriptionId
              RatePlanChargeId
              TaxAmount
              TaxCode
              TaxMode
              UnitPrice
              UOM
              ChargeDate
              AdjustmentRevenueAccountingCodeId
              ContractAssetAccountingCodeId
              ContractLiabilityAccountingCodeId
              ContractRecognizedRevenueAccountingCodeId
              UnbilledReceivablesAccountingCodeId
              RevRecCode
              RevRecStartDate
              RevRecTriggerCondition
              DefaultPaymentMethodId
              ItemType
              JournalEntryId
              TaxExemptAmount
              SoldToContactId
              SoldToContactSnapshotId
              BillToContactId
              BillToContactSnapshotId
              RatePlanId
              ProductId
              ProductRatePlanId
            }
          }
        }
      }
    }
  }
}
```

**Variables and bindings:**

| Variable | Type | Value |
|---|---|---|
| `$filter` | `invoiceFilterInput` | `{ field: "Id", operator: "EQ", value: "<invoice_id>" }` if the key is 32 hex chars; `{ field: "InvoiceNumber", operator: "EQ", value: "<key>" }` otherwise. |

`pageSize: 1` on the root is a literal slot (fetches one invoice). `pageSize: 10` on `invoiceitems` is a literal slot — replace with the customer's desired page size (1–99). Both are integer literals in the document, not variables.

**Adaptation to v2 output:**

Key mappings (GraphQL field → v2 field):
- `ChargeAmount` → `amount`
- `ProcessingType` → `discount_item` (boolean: `ProcessingType === "Discount"`)
- `DeferredRevenueAccountingCode.GLAccountName` → `deferred_revenue_account` (string or undefined if absent)
- `RecognizedRevenueAccountingCode.GLAccountName` → `recognized_revenue_account`
- `AccountReceivableAccountingCode.GLAccountName` → `accounts_receivable_account`
- `TaxMode` → `tax_inclusive` (boolean: `TaxMode === "TaxInclusive"`)
- `customFields[{key,value,type}]` → `custom_fields` object (see §3.5)
- `InvoiceId` on the item → `invoice_id` (do not use the parent node's `Id` for the child's `invoice_id`)

The parent node exposes only `Id` (used as an attachment key); a child's `invoice_id` always comes from the child's own `InvoiceId` field.

**Known differences and what is NOT covered:**

- `AccountingCode` (v2 `accounting_code`) has no GraphQL field name in the object metadata — the adapter emits it only if the raw data happens to supply it; it is not selected in this query.
- Taxation items (`taxationItems`, `credittaxationitems`) are not selected; the adapter produces `undefined` for them.
- Populated `Invoice`, `Subscription`, `OrderLineItem`, and `RatePlanCharge` branches on the item are not selected.
- No nested cursor replay; the nested `endCursor` is output-only.
- This is the first page of items only. For subsequent pages, a separate paging mechanism (e.g. GP-2 list pattern) is needed; there is no direct nested-cursor replay in this vetted query.

**Caveat:** source-observed; not a server contract.

---

### GP-2: Invoice items, list with per-parent items and root cursor

**When to use:** The customer is calling `invoices.list` and needs the `items` expansion with a cursor for paging through the invoice list. Use GP-2 when fetching multiple invoices with their nested items and needing to advance through invoice pages.

**Vetted document:**

```graphql
query getInvoices($filter: invoiceFilterInput, $cursor: String, $orderBy: [invoiceSortInput]) {
  invoices(pageSize: 30, filter: $filter, cursor: $cursor, orderBy: $orderBy) {
    pageInfo {
      endCursor
    }
    edges {
      node {
        Id
        invoiceitems(pageSize: 10) {
          pageInfo {
            endCursor
          }
          edges {
            item: node {
              customFields { key value type }
              CreatedById
              UpdatedById
              CreatedDate
              Id
              UpdatedDate
              ChargeAmount
              BookingReference
              AppliedToInvoiceItemId
              ProductRatePlanChargeId
              ProcessingType
              DeferredRevenueAccountingCode { GLAccountName }
              Description
              InvoiceId
              SKU
              ChargeName
              PurchaseOrderNumber
              Quantity
              RecognizedRevenueAccountingCode { GLAccountName }
              Balance
              RevenueRecognitionRuleName
              ServiceEndDate
              ServiceStartDate
              AccountReceivableAccountingCode { GLAccountName }
              SubscriptionId
              RatePlanChargeId
              TaxAmount
              TaxCode
              TaxMode
              UnitPrice
              UOM
              ChargeDate
              AdjustmentRevenueAccountingCodeId
              ContractAssetAccountingCodeId
              ContractLiabilityAccountingCodeId
              ContractRecognizedRevenueAccountingCodeId
              UnbilledReceivablesAccountingCodeId
              RevRecCode
              RevRecStartDate
              RevRecTriggerCondition
              DefaultPaymentMethodId
              ItemType
              JournalEntryId
              TaxExemptAmount
              SoldToContactId
              SoldToContactSnapshotId
              BillToContactId
              BillToContactSnapshotId
              RatePlanId
              ProductId
              ProductRatePlanId
            }
          }
        }
      }
    }
  }
}
```

**Variables and bindings:**

| Variable | Type | Value |
|---|---|---|
| `$filter` | `invoiceFilterInput` | Optional; filter by invoice fields. |
| `$cursor` | `String` | The `endCursor` value from the previous response's `invoices.pageInfo.endCursor`; omit on the first page. |
| `$orderBy` | `[invoiceSortInput]` | Optional sort specification. |

`pageSize: 30` on the root and `pageSize: 10` on `invoiceitems` are literal integer slots. Replace with the customer's `page_size` value (1–99; note: the v2 implementation applies the same `page_size` to both — see GP-4).

**Adaptation to v2 output:**

The v2 `next_page` output field is `res.data.invoices.pageInfo.endCursor`. The `data` array is built by mapping `res.data.invoices.edges` and adapting each `edge.node`. Each parent's items are adapted independently (per-parent ownership; items are never merged across parents).

**Known differences:**

- Each parent's nested items are the first page only (nested `endCursor` is output but not replayed in this vetted query).
- No independent child-cursor replay (see §3.3).

**Caveat:** source-observed; not a server contract.

---

### GP-3: Account `bill_to` and `sold_to` contacts

**When to use:** The customer needs the `bill_to` or `sold_to` contact on an account (`accounts.get` with `expand[]=bill_to` or `expand[]=sold_to`). v1 REST returns contacts embedded in the account response; the Object Query REST account endpoint does not surface these as expandable contacts in the same shape as v2.

**Vetted document — bill-to:**

```graphql
query getAccountBillTo($filter: accountFilterInput) {
  accounts(pageSize: 1, filter: $filter) {
    edges {
      node {
        Id
        BillTo {
          customFields { key value type }
          CreatedById
          UpdatedById
          CreatedDate
          Id
          UpdatedDate
          AccountId
          Address1
          Address2
          Country
          City
          State
          PostalCode
          County
          HomePhone
          FirstName
          LastName
          PersonalEmail
          WorkEmail
          NickName
          OtherPhone
          WorkPhone
          MobilePhone
          TaxRegion
          OtherPhoneType
          Fax
        }
      }
    }
  }
}
```

**Vetted document — sold-to:**

```graphql
query getAccountSoldTo($filter: accountFilterInput) {
  accounts(pageSize: 1, filter: $filter) {
    edges {
      node {
        Id
        SoldTo {
          customFields { key value type }
          CreatedById
          UpdatedById
          CreatedDate
          Id
          UpdatedDate
          AccountId
          Address1
          Address2
          Country
          City
          State
          PostalCode
          County
          HomePhone
          FirstName
          LastName
          PersonalEmail
          WorkEmail
          NickName
          OtherPhone
          WorkPhone
          MobilePhone
          TaxRegion
          OtherPhoneType
          Fax
        }
      }
    }
  }
}
```

**Variables and bindings:**

| Variable | Type | Value |
|---|---|---|
| `$filter` | `accountFilterInput` | `{ field: "Id", operator: "EQ", value: "<account_id>" }` if the key is 32 hex chars; `{ field: "AccountNumber", operator: "EQ", value: "<key>" }` otherwise. |

`pageSize: 1` is a literal slot (fetches one account).

**Adaptation to v2 output:**

The adapter produces a 20-key output object from 25 selected scalars. `contactType` (`"bill_to"` or `"sold_to"`) is injected at the model layer, not by the transform. `OtherPhoneType` is reverse-mapped through an enum. Custom fields follow the standard helper (§3.5).

**Null custom-field behavior (v2 default):** the default behavior (`PRESERVE_NULL_CUSTOM_FIELDS` defaults to `true`) preserves null custom-field values as `null` in the output. Only the literal string `"false"` triggers the legacy rollback path that coerces null numerics to `0`. The v2 default is null-preserving.

**Known differences:**

- `BillTo`/`SoldTo` are direct objects (not connections); there are no edges, paging, or cursor on the contact itself.
- `Description` is not a contact field in the metadata and is not selected.
- `bill_to` and `sold_to` are separate queries; they cannot be combined into one query document in this vetted pattern.

**Caveat:** source-observed; not a server contract.

---

### GP-4: `page_size` applying to root and nested lists when `expand[]` is used

**When to use:** The customer is using `invoices.list` or `invoices.get` with `expand[]=items` and expects `page_size` to control both the root invoice page and the nested items page. v1 REST `pageSize` sizes only the root invoices list; public Object Query REST `pageSize` also sizes only the root connection. v2 applies the same `page_size` to both.

**Guidance:**

In v2, when `expand[]=items` is supplied, `page_size` fills two literal slots: the root `invoices(pageSize: N)` and the nested `invoiceitems(pageSize: N)`. Both integer literals in the query document are set to the same value (`args.pageSize || 30` at the root, `args.pageSize || 10` at the nested connection).

When adapting GP-1 or GP-2 for a customer who supplies `page_size`, replace both `pageSize` integer literals with the supplied value. There is no separate variable for child page size; the two slots must be set to the same value.

**What is NOT covered:**

- Independent root vs nested page sizes (v2 does not support them; neither does this pattern).
- Nested paging beyond the first items page per parent (the nested cursor is output-only; see §3.3).

**Caveat:** source-observed; not a server contract.

---

### GP-5: Root `cursor` pass-through

**When to use:** The customer is paging through `invoices.list` (or another list operation) and needs to pass a cursor to advance to the next page.

**Guidance:**

The `cursor` query parameter from the v2 request is passed directly into the `$cursor` variable of the GP-2 query. The root connection receives `cursor: $cursor`. On the first request, omit the variable. On subsequent requests, supply the value of `invoices.pageInfo.endCursor` from the previous response as the `$cursor` variable.

The nested items connection (`invoiceitems`) does not receive the cursor variable. Never substitute a nested `endCursor` into `$cursor` on a subsequent call; these are separate cursor spaces.

**What is NOT covered:**

- Cursor replay for nested connections (vetted pattern does not implement it; there is no corresponding recipe).

**Caveat:** source-observed; not a server contract.

---

### GP-6: Accounting-code GL account names on invoice items

**When to use:** The customer needs `deferred_revenue_account`, `recognized_revenue_account`, or `accounts_receivable_account` on invoice items. v1 REST and public Object Query REST return accounting-code IDs (e.g. `deferredRevenueAccountingCodeId`), not names. v2 returns the GL account name. Use this pattern to explain how v2 obtains names via GraphQL.

**Guidance:**

The three GL account name fields are nested objects in the GraphQL selection:

```graphql
DeferredRevenueAccountingCode { GLAccountName }
RecognizedRevenueAccountingCode { GLAccountName }
AccountReceivableAccountingCode { GLAccountName }
```

These appear in both GP-1 and GP-2 (see §4 above). The adapter extracts the `GLAccountName` child via optional chaining:

```
deferred_revenue_account: DeferredRevenueAccountingCode?.GLAccountName ?? undefined
recognized_revenue_account: RecognizedRevenueAccountingCode?.GLAccountName ?? undefined
accounts_receivable_account: AccountReceivableAccountingCode?.GLAccountName ?? undefined
```

If the server returns `null` or omits the accounting-code object, the v2 output field is `undefined` (absent). Customers who currently read accounting-code names from v2 should use the full GP-1 or GP-2 query (which selects all three) rather than constructing a narrower query.

**What is NOT covered:**

- `AccountingCode` (v2 `accounting_code`) has no GraphQL field name in the object metadata and is not selected in the vetted queries.
- Any accounting-code-name expansion on resources other than invoice items (credit memo items, debit memo items) is not covered by this entry; separate recipes and claims would be needed.

**Caveat:** source-observed; not a server contract.

---

### GP-7: Field narrowing — v2 narrows the fetch selection and then projects

**When to use:** The customer is using `fields[]` or `<object>.fields[]` to request a subset of output fields and expects only those fields to be fetched from the server. v2 narrows the GraphQL selection to only the requested fields before sending the query. Public Object Query REST `fields[]` (if supported) may narrow the response, but v2's GraphQL path narrows the upstream fetch. Use this entry to explain the behaviour and its limits.

**Guidance:**

v2 processes `fields[]` in two stages:

1. **Fetch narrowing (upstream):** The v2 implementation translates v2 field names to GraphQL field names using the object metadata, then passes the translated list to the query builder. The query builder includes only the requested GraphQL fields in the selection set. If no `fields[]` parameter is supplied, the full default field set is used.

2. **Output projection (downstream):** A downstream projection filter further filters the adapter output to the requested v2 field names, concatenating top-level `fields[]` and any expansion path tokens. This projection runs on the already-adapted output object.

**What a customer can do:** Supply `invoice.fields[]` (or `fields[]` for the top-level resource) with v2 field names. The agent should show the customer only the fields that are in the metadata map for the object type. Fields not present in the metadata map will raise a validation error.

**What is NOT covered:**

- Narrowing on nested/child fields via `invoiceitems.fields[]` is not covered by the vetted recipe (the recipe uses a fixed full-core selection for the child items connection).
- The vetted GP-1/GP-2 queries use a fixed full-core child selection (overfetch); a customer who supplies `fields[]` will see the projection applied to the full-core fetch, not a narrower upstream fetch for the items child.
- No independent GraphQL field-narrowing recipe exists for nested connections other than the fixed full-core sets in GP-1 and GP-2.

**Caveat:** source-observed; not a server contract.

---

## 5. GP-none cases

The following cases have no vetted GraphQL query. The agent must tell the customer there is no vetted example and follow the row's limitation text. **Do not invent a query.**

| Case | Reason |
|---|---|
| `zuora-cache-enabled` header | This is an internal header set by the v2 client on every call. There is no public equivalent and no GraphQL mechanism for cache control. |
| Multi-field sort (`sort[]` with more than one field) | v2 passes a single sort to the root OQ connection. No vetted multi-field sort recipe or v2 source exists for more than one sort field. |
| OR filter across different fields (`filter[]` with OR across distinct fields) | Public Object Query filter grammar does not document OR across different fields. No vetted recipe or v2 source evidence exists. |
| Nested item paging beyond the first page (nested cursor replay) | The vetted recipes output the nested `endCursor` but never replay it. No vetted recipe for nested cursor replay exists in the in-repo assets. |
| Any expansion other than `items` on invoices | Only the `items` (`invoiceitems`) nested connection is covered by the vetted GP-1/GP-2 recipes. Other nested connections (e.g. `taxation_items`) are not covered. |
| Accounting-code names on non-invoice-item objects | GP-6 covers invoice items only. |
| Any case without in-repo v2 source evidence | If the behavior cannot be traced to the vetted v2 snapshot, it is GP-none. |

---

## 6. How an agent uses this reference

1. **Find the GP id on the row.** Each field-map row or limitation entry that has a GraphQL alternative carries a `GP-<n>` id or `GP-none`. Locate the matching entry in this document.

2. **For GP-none:** tell the customer that no vetted GraphQL example is available for this case. Follow the row's limitation text exactly. Do not construct a query.

3. **For GP-`<n>`:** show the customer the vetted document from the entry and explain the variable bindings. Do not extend the query beyond the vetted shape without explicitly telling the customer that the extension is unvetted and not covered by this reference.

4. **Always state the caveat:** Object Query GraphQL is public but undocumented; the evidence is source-observed from the v2 implementation; this is not a server contract. The customer's implementation must use their own transport and credentials, check HTTP status and `errors` independently, and treat absent keys as distinct from `null`.

5. **Do not copy MCP tool names, tenant data, credentials, endpoint URLs, or internal v2 header values** into any generated code or guidance derived from this document.
