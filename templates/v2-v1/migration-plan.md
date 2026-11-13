# v2 → Public API Migration Plan

**Generated:** {date}
**Codebase analyzed:** {path}
**Pack version:** {pack_version}

---

## Summary and coverage

| Category | Count |
|---|---|
| Sites matched to pack ids | {n} |
| Migration cards (one per v2 operation) | {n} |
| Sites with limitations | {n} |
| Parameters / fields not covered | {n} |
| Needs human review | {n} |
| Undetected risk entries | {n} |
| Languages without SDK patterns | {list} |

| Card | v2 operation | Sites | Status | What you must decide |
|---|---|---|---|---|
| {pack_id} | {METHOD /v2/path} | {n} | {Likely / Needs human / Not available in v1} | {decision or "none"} |

Status values: **Likely** = every parameter and field this customer uses has a confirmed mapping, or a limitation with a stated mapping, and no decision is open. **Needs human** = a limitation without a stated mapping, a GraphQL-only item, a required input the old call did not send, or anything not covered. **Not available in v1** = a used item has no public equivalent. **Verified** is set only by `/zuora-v2-migration-verify` after a sandbox parity run on sampled records; this plan does not include one.

---

## Open decisions and limits

- Decisions still open for the customer:
- Tool and pack disagreements (operation, what the tool said, what the pack says; "None" if none):
- Parameters / fields that could not be mapped, and why:
- Nothing in this plan was verified against a tenant.

---

## Implementation choice

| Language | Customer's current style | Default chosen | Alternatives | Consequences of each option (what callers must change; computed fields, limitations and enum changes must be rebuilt under every option) | Evidence about SDK support |
|---|---|---|---|---|---|

### Question for the customer

- Question (as asked, or as it would have been asked):
- Default:
- Options and the consequences of each:
- Answer (if asked):

---

## Inventory table

| Site ID | File | Line | Pack ID | Route | Call style (raw HTTP, SDK, wrapper, config, export) | Request parameters sent | Response fields read | Confidence |
|---|---|---|---|---|---|---|---|---|
| S001 | src/Client.java | 42 | accounts.get | public_oq | raw HTTP | expand[]=bill_to | account_number, remaining_invoice_balance | high |

---

## Migration cards

<!-- One card per distinct v2 operation (pack id and route), however many call sites it has. Left = what the customer uses today, right = what replaces it. -->

### Card {pack_id}: {METHOD /v2/path} → {public route}

**Status:** {Likely / Needs human / Not available in v1} — {one line why}
**Route:** {route} — {rationale from the pack}
**Occurrences ({n}):** {file:line, file:line, ...} (details in "Per-site changes")

#### Request: what you send today and what replaces it

| v2 parameter (as sent) | Disposition | Public parameter | Transform and notes |
|---|---|---|---|

Public path and steps: {path(s) from the route file; one v2 call may become several}
Headers and auth: {only what the route file's unsupported[] notes state}
Required inputs the old call did not send: {or "none"}

#### Response: what you read today and where it lives now

| v2 field (read by your code) | Disposition | Public field | Transform and notes |
|---|---|---|---|

v2 response fields your code does not read: {compact list of v2 names from the route file}
Public response fields on this route that your code does not read today: {compact list of the public field names from the route file; the complete schema is in the API reference}
Computed or unavailable fields: {paid, past_due, ...; derived from which public fields, or not rebuildable}

#### Differences

- Input: {filters, sort, expand names, key formats}
- Output: {regrouped, renamed, retyped, missing fields, paging}
- Paging: {cursor and page-size parameter names, bounds, three cursors for billing documents, and so on}
- Errors: see "Error handling by route"; differences specific to this operation: {or "none"}
- Limitations: names only, see "Limitations"; GraphQL pointers (GP-n, with the caveat "Object Query GraphQL is public but undocumented; the evidence is source-observed"): {or "none"}

---

## Error handling by route

{One table per route used, with the six situations: not_found, invalid_filter_or_enum, invalid_page_size_or_cursor, malformed_identifier, authorization_failure, server_error_retry. Columns: situation, v2 behavior, route behavior, migration note.}

---

## Limitations

{Each limitation note once: kind, reason, guidance, GP-n pointer if any, and the cards and sites it affects.}

---

## GraphQL pointers

{The vetted GraphQL documents for the GP-n items this code uses, copied from the pack; the per-site diff POSTs them as raw HTTP in the customer's language. Write "None" when no item points to GraphQL.}

---

## Per-site changes

<!-- Repeat the block below for each site. Only what is specific to the site; everything per operation is in its card. -->

### Site {id}: {file}:{line}

**Card:** {pack_id}
**Call site:** `{matched_text}`
**Language:** {language}

#### Facts read from the code

- Request parameters sent:
- Response fields read:
- Paging loop present (yes/no, how):
- Error handling around the call:
- Downstream consumers of the response:

#### Proposed diff

```diff
{Language-appropriate diff showing the rewrite for this site.}
```

#### Open questions

{Items the implementer must verify before applying the rewrite.}

---

## Handoff packs

<!-- One block per system the agent cannot edit (an export of an integration tool such as Boomi, Workato or Power Automate, or a Postman collection). Nothing is rewritten for these: no file under proposed/. Write "None" when every site is code or config the agent can edit. -->

### Handoff pack: {system}, {export file}

**Status: Unverified. Written from the export file; nothing was tried in {system} and nothing was rewritten.**
**Sites:** {site ids and the export file lines}
**Cards:** {pack ids}

#### Where to change it

{The step, action or request of the export that sends the call, named as the export shows it. Write "to confirm in {system}" for anything the export does not show.}

#### v1 request to use

{Method, public path, query parameters, headers and authentication, from the card.}

#### Field mapping

| v2 field the tool reads | Public field | Transform and notes |
|---|---|---|

#### What we still need from you

{Only when the export does not show which response fields or values the tool reads: name the exact item to send back, in the tool's terms, so the field mapping can be completed (for example the response profile of the step, the datapills later steps use from it, or the fields a test asserts on). Write "Nothing" when the mapping above is complete.}

#### Steps

1. {Step in the tool's own terms.}

#### Test checklist

- [ ] {What to run in the tool, and what result means the change is correct.}

---

## Not covered and needs-human

| Site ID | Parameter / Field | Reason |
|---|---|---|

---

## Undetected risk

| File | Line | Kind | Note |
|---|---|---|---|

---

*This plan is generated from the Zuora v2 to public API mapping pack (version {pack_version}).
All proposed changes are sourced from the pack; they are confirmed or limitation only.
Do not commit this file to your repository — it may contain customer-specific code snippets.*
