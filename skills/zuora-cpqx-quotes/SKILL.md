---
name: zuora-cpqx-quotes
description: Applies to CPQ X only. Create, amend, renew, cancel, edit, price, preview, or submit real Zuora Quotes (CPQ X / Quote Studio) quotes in the user's Salesforce org, and look up CPQ accounts or catalog rate plans, using the manage_cpqx_quotes tool.
allowed-tools: [Read, AskUserQuestion, mcp__zuora-mcp__manage_cpqx_quotes]
---

# Zuora Quotes (CPQ X)

**Applies to: CPQ X only.** Editions and terms are defined in `${CLAUDE_PLUGIN_ROOT}/references/cpq-editions.md`; read it if the edition is unclear. This skill does not work on legacy CPQ orgs.

Work with live quotes in the user's Salesforce org through the `manage_cpqx_quotes` zuora-mcp tool. This skill is for operating on quote data. For writing Apex, LWC, or Quote Studio customization code, use `zuora-cpq-context` instead.

## Setup check

The Salesforce org is connected once per Zuora tenant by a Zuora admin; users never log in to Salesforce or handle credentials. Never ask the user to paste a client secret, access token, or password into the chat, and never write credentials to any file.

If you are unsure what the org supports, call `get_cpqx_capabilities` first. On any of the errors below, stop and tell the user plainly what it means; most need a Zuora admin, not the user, to act:
- `SALESFORCE_NOT_CONNECTED`: this tenant has no Salesforce connection. A Zuora admin must connect the tenant's Salesforce org in Zuora (connectors).
- `SALESFORCE_REAUTH_REQUIRED` or `SALESFORCE_CONNECTION_REVOKED`: the connection exists but an admin must authorize or reconnect it.
- `SALESFORCE_CONNECTOR_INACTIVE`: the Salesforce connector is switched off for the tenant; an admin must turn it on.
- `SALESFORCE_CONNECTION_FORBIDDEN`: the user may not use the tenant's connection; ask an admin for access.
- `SALESFORCE_TOKEN_EXCHANGE_FAILED`: Salesforce refused the stored credentials; an admin must check the connection.
- `SALESFORCE_NO_TENANT`: the request did not reach Zuora through the Zuora MCP endpoint; check `ZUORA_BASE_URL`.
- `CPQX_NOT_ENABLED`: the connected org is not on CPQ X (Quote Studio is not enabled), so this skill cannot work there. Stop, tell the user the org is not CPQ X, and do not retry or fall back to another tool.
- `UNKNOWN_ENDPOINT`: the org's Zuora Quotes package must be upgraded to a version that includes the quote API; tell the user to upgrade it.
- `INSUFFICIENT_OBJECT_PERMISSIONS` or `SALESFORCE_ACCESS_DENIED`: the Salesforce user behind the connection lacks Zuora Quotes permissions, or the connection is read-only (a connection taken only from Billing's CPQ profile may be labelled read-only); an admin must fix the Salesforce user's permissions or the connection.
- `SALESFORCE_CONNECTION_UNAVAILABLE`: temporary; Zuora could not look the connection up right now. Nothing was sent to Salesforce, so repeat the same call once after a few seconds.
- If `manage_cpqx_quotes` is not available at all: zuora-mcp is not connected or CPQ X quoting is not enabled on the server; check `ZUORA_BASE_URL`, `ZUORA_CLIENT_ID` and `ZUORA_CLIENT_SECRET` first.

## Rules

- Use Salesforce IDs the user gives you as they are (do not search for an ID). Resolve any other ID with a lookup: `find_cpqx_accounts` for accounts, `search_cpqx_catalog` for product rate plans, `get_cpqx_quote` for quote rate plan and charge IDs. Never guess or invent Salesforce IDs.
- If a lookup returns several plausible matches, ask the user to choose.
- Amend, renew, and cancel need the Salesforce account ID and the Zuora subscription number (for example `A-S00000123`). Ask for the subscription number if the user did not give it. These three operations take no products: to change products on an amendment or renewal, call `add_cpqx_quote_products`, `update_cpqx_quote_charges`, or `remove_cpqx_quote_products` on the returned quote ID. An amendment with no product change is refused on submit (`NO_AMENDMENTS`).
- Writes do not price the quote. After any create, amend, renew, cancel, add, update, or remove, call `preview_cpqx_quote` for that quote (one quote per call); it prices the quote and returns `pricingStatus`. Then call `get_cpqx_quote`; when `pricingStatus` is `READY` it includes `metrics` (MRR, TCV, totals, and the delta MRR/TCV against the subscription) to show the user. Metrics are saved a few seconds after preview returns, so if it still says `PENDING`, wait 3-5 seconds and check again, for up to about 30 seconds. If preview returns `FAILED`, report its `pricingError` to the user as given. Every edit sets `pricingStatus` back to `PENDING` until the next preview. A large quote is priced by a background job: if preview returns `PENDING` with an `asyncJobId` and `pricingJobId`, poll `get_cpqx_preview_status` with that `pricingJobId` every few seconds until `pricingJobStatus` is `COMPLETED` or `FAILED`. On `COMPLETED`, call `preview_cpqx_quote` once more with the same `quoteIds` and that `asyncJobId`; only that call saves the price, and never start a new preview for the same quote while the job runs. On `FAILED`, stop and tell the user. If the status check says `FAILED` with `errorCode` `PREVIEW_STALE`, or the second `preview_cpqx_quote` call is refused with `PREVIEW_STALE`, the quote changed while it was pricing and nothing was saved: do not poll or continue that job again, call `preview_cpqx_quote` once more without `asyncJobId`, and tell the user the quote changed. Submit only after the preview is `READY`; submitting a large quote is processed in the background, so `submit_cpqx_quote` answers `PROCESSING` and `get_cpqx_quote` shows `SUBMITTED` when it finishes. If preview returns `warnings` (more than 50 charges), tell the user: Zuora recommends at most 50 rate plan charges per subscription, so large quotes are slower. A preview with nothing to price (an amendment with no change) says so in `pricingError`.
- Amend and renew quotes load the subscription's existing plans in the background (about 20 seconds). After creating one, call `get_cpqx_quote` until `existingPlansLoading` is `false` before editing or previewing; an early preview just answers `PENDING` with `existingPlansLoading: true`. If `existingPlansLoadStatus` is `FAILED` (or `preview_cpqx_quote` returns `EXISTING_PLANS_LOAD_FAILED`), stop and tell the user; do not create another quote unless they ask.
- Cancel quotes hold no plan rows (that is how Quote Studio works). Preview a cancel quote, then read `metrics`: the negative `deltaMrr` and `deltaTcv` are the cancellation impact to show the user before submitting.
- A renewal's `metrics` show the renewed term (for example MRR and TCV for the whole renewal term); its delta is 0 unless you changed products.
- Write operations are never retried automatically. After a timeout, call `get_cpqx_quote` to see what happened before trying again, so you do not create a duplicate quote.
- Creating, amending, renewing, cancelling, editing and pricing only change the quote in Salesforce (CPQ). Nothing reaches Zuora billing until `submit_cpqx_quote`.
- Call `submit_cpqx_quote` only when the user explicitly asks to submit or send the quote to Zuora or billing (for example "submit this quote", "send it to Zuora", "send to billing"). Never submit as part of a create, amend, renew or cancel request, never submit on your own initiative, and do not treat approval of the quote's content ("looks good", "ok") as a request to submit.
- A quote can be sent at any time after it is created, including days later. Before submitting, call `get_cpqx_quote` and show the account, plans and `metrics`, and say that sending creates an order and subscription in Zuora and cannot be undone.
- Ask for confirmation exactly once. In Claude Code, this plugin shows the user an approval prompt for every `submit_cpqx_quote` call: show the summary, then call `submit_cpqx_quote`, and let that prompt be the confirmation (do not also ask in chat). In other clients, ask once in chat ("Send this quote to Zuora?") and call `submit_cpqx_quote` only after a yes. If the user declines, do not submit.
- If the org requires approval, the submit is refused with `NOT_APPROVED`: tell the user to approve the quote in Salesforce (you cannot approve it), then submit again.
- `QUOTE_PENDING_APPROVAL`: the quote is waiting for approval and cannot be edited. Do not retry; tell the user to finish the approval in Salesforce first.
- `OWNERSHIP_CHECK_UNAVAILABLE`: Salesforce could not confirm that the billing account belongs to the Salesforce account, and nothing was changed. Retry once after a short wait; if it fails again, tell the user.
- `QUOTE_RAMP_NOT_SUPPORTED`: the quote has ramp intervals or charge segments, so its products and charges cannot be changed here. Do not retry; tell the user to change it in Quote Studio.
- Quote details at creation: by default `create_cpqx_quote` uses the org's default settings. Pass `quoteName` (1-80 characters; the user's chosen name for the quote), `billToContactId`, `soldToContactId`, `startDate` (yyyy-MM-dd), `subscriptionTermType` (Termed/Evergreen), `initialTerm`, `initialTermPeriodType` (Month/Year/Day/Week), `renewalTerm`, `renewalTermPeriodType` and `autoRenew` only when the user asks for them. Never invent values. Evergreen quotes take no term fields.
- Contacts: a "bill to" and "sold to" can be the same or different contact. Use the contacts from `find_cpqx_accounts`; if the account has many (`contactsTruncated`), call `find_cpqx_contacts` with a name or email. If several match, ask the user to choose. Never guess a contact id.
- After create or update, call `get_cpqx_quote` and show `quoteDetails` (contacts, start date, terms) with the pricing. If `missingForSubmit` lists items (for example contacts or start date), tell the user what is missing and offer to set it with `update_cpqx_quote`.
- `productRatePlanIds` takes at most 50 per `create_cpqx_quote` or `add_cpqx_quote_products` call. For more products, call `add_cpqx_quote_products` several times; a quote can hold many more than 50.
- Term rules by quote type: new and amend quotes take all term fields. A renew quote takes only `renewalTerm`, `renewalTermPeriodType` and `autoRenew`: its initial term is the term being renewed and is refused. A cancel quote takes no term fields.
- To change details on an existing quote, use `update_cpqx_quote` (see `updatableQuoteFields`). Do not create a second quote for that. It is refused for submitted quotes. After it, preview again.
- If `create_cpqx_quote` or `update_cpqx_quote` returns `UNKNOWN_ENDPOINT` or says a field is not supported, the org's package is too old for it: tell the user an admin must upgrade Zuora Quotes. Do not retry.
- Work on one quote at a time unless the user asks for more.

## Workflows

**New subscription quote**
1. `find_cpqx_accounts` with the customer name.
2. `search_cpqx_catalog` for each product the user wants.
3. If the user named contacts, call `find_cpqx_contacts` (when the account has many) to get ids.
4. `create_cpqx_quote` with `accountId` and, optionally, `productRatePlanIds`, `opportunityId`, `zuoraAccountId`, and only the details the user asked for (`quoteName`, `billToContactId`, `soldToContactId`, `startDate`, `subscriptionTermType`, `initialTerm`, `initialTermPeriodType`, `renewalTerm`, `renewalTermPeriodType`, `autoRenew`). Otherwise leave them out so defaults apply.
5. `preview_cpqx_quote`, then `get_cpqx_quote`, and show the result with `quoteDetails`. If the user later wants different details, use `update_cpqx_quote` on the same quote. Stop here: the quote stays in Salesforce until the user asks to send it to Zuora.

**Change an existing subscription**
1. `find_cpqx_accounts`, then `amend_cpqx_quote`, `renew_cpqx_quote`, or `cancel_cpqx_quote` with `accountId` and `subscriptionNumber`.
2. Amend and renew: wait until `get_cpqx_quote` shows `existingPlansLoading` false (if `existingPlansLoadStatus` is `FAILED`, stop and tell the user). Amend: add or edit products (an amendment with no change is refused). Renew: edit only if the user wants changes.
3. `preview_cpqx_quote`, then `get_cpqx_quote`, and show the result (for cancel, the negative delta is the impact). Stop here: the quote stays in Salesforce until the user asks to send it to Zuora.
- Effective date (set it when you create the quote, step 1): `amend_cpqx_quote` and `cancel_cpqx_quote` take an optional `effectiveDate` (yyyy-MM-dd, today or later). Pass it only when the user gives a date; never guess one. Read `effectiveDate` from the response and confirm it to the user. For cancel, remind the user the subscription ends on that date once submitted. Renew takes no date: a renewal starts when the current term ends.
- Amending a subscription that was already renewed starts in the renewed term, so only products effective on that date can be added.

**Edit a quote**
- Add products: `add_cpqx_quote_products` with `productRatePlanIds` from `search_cpqx_catalog`.
- Change quantity, price or discount: `update_cpqx_quote_charges` with `chargeUpdates` items of `quoteRatePlanChargeId` (from `get_cpqx_quote`) and `fields`. Field values are the NEW absolute values, not increments: read each charge's current `quantity`, `listPrice`, `effectivePrice`, `discount` and `total` from `get_cpqx_quote`, then compute (for example current quantity 3, "add 5 seats" means `{"Quantity__c": 8}`). The editable fields are listed in `updatableChargeFields`: `Quantity__c`, `ListPrice__c`, `EffectivePrice__c`, `Discount__c`, `Total__c`. A discount and a unit price are one setting seen two ways (discount percent = (list price - effective price) / list price), so setting one changes the other; the last one set wins.
- A quote with `isMultiSubscription: true` cannot be edited or previewed with these tools; tell the user to use Quote Studio.
- Remove products: `remove_cpqx_quote_products` with `quoteRatePlanIds` from `get_cpqx_quote`. Each plan there also shows the catalog `productRatePlanId` it was built from, so match a plan to a catalog product by that id, not by name. If the same product was added twice, those lines share name and `productRatePlanId` and differ only by `quoteRatePlanId`; use `quoteRatePlanId` to remove or edit one of them.
- Preview again after every edit.

## Output

Keep replies short: quote ID, quote type, pricing status, the products and charges that changed, and MRR, TCV, and total when `READY`. Do not echo raw tool JSON unless the user asks for it.
