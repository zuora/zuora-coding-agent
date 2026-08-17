# CPQ JavaScript State Model

Quote Studio extensibility components commonly receive public `@api` state properties.

## Known public properties

- `quoteState`: Quote, product timelines, subscriptions, charges, and calculated quote state.
- `pageState`: Quote Studio page and rules data. Rule fields require the relevant CPQ X Rule Fields field set entries.
- `metricState`: Quote metrics available to the custom component.
- `masterQuoteState`: Master quote context for MSQ scenarios where available.
- `parentQuoteState`: Parent quote context for MSQ scenarios where available.
- `ZQFClient`: Quote Studio client helper module for quote-state traversal and mutation event construction when Zuora managed package version is 10.58 or later. Import from `zqu/zqfClient`.

## Required headless component state properties

For non-MSQ headless components, include all of these public properties:

```js
@api quoteState;
@api metricState;
@api pageState;
```

When MSQ is enabled or the implementation uses MSQ hooks or child quote context, include all non-MSQ properties plus:

```js
@api masterQuoteState;
@api parentQuoteState;
```

When the target Zuora managed package version is 10.58 or later and the implementation reads, updates, or fires quote state changes through the Quote Studio client helper, import and construct `ZQFClient`:

```js
import ZQFClient from 'zqu/zqfClient';

get zqf() {
  return ZQFClient.from(() => this.quoteState, {
    pageState: () => this.pageState
  });
}
```

## Quote state navigation hierarchy

CPQ quote state is deeply nested. Generated code must resolve the correct path for each object type or use documented `ZQFClient` read helpers instead of guessing nested property names.

**Top-level `@api` properties**

- `quoteState` — quote, product timelines, subscriptions, charges, tiers, and calculated quote data.
- `pageState` — Quote Studio page and rules data.
- `metricState` — quote metrics exposed to custom components.
- `masterQuoteState` / `parentQuoteState` — MSQ child/parent quote context when applicable.

**Wrapper objects and `.record`**

Timeline, rate plan, charge, tier, and amendment objects returned by `ZQFClient` read helpers are wrapper objects. Salesforce field values live on `.record`:

- Quote fields: `this.zqf.getQuote()` or `this.zqf.getQuoteField('zqu__InitialTerm__c')`
- Rate plan fields: `ratePlan.record.Name`, `ratePlan.record.zqu__ProductRatePlan__c`
- Charge fields: `charge.record.zqu__Quantity__c`, `charge.record.Name`
- Tier fields: `tier.record.zqu__Discount__c`, `tier.record.zqu__StartingUnit__c`

Do not read `charge.zqu__Quantity__c`, `charge.Name`, `ratePlan.Name`, or `tier.zqu__Discount__c` directly on wrapper objects.

**Object maps vs arrays**

Several nested collections on `quoteState` are object maps keyed by ID, not JavaScript arrays:

- `quoteState.productTimelines` — keyed by timeline ID. Use `this.zqf.getProductTimelines()` for array iteration.
- Do not use `for...of`, `.map(...)`, `.forEach(...)`, or spread syntax directly on `quoteState.productTimelines`.

**Prefer helpers over manual traversal**

For package version 10.58 or later, prefer documented `ZQFClient` read helpers before walking nested quote state manually:

- Timelines: `getProductTimelines()`, `getTimeline(timelineId)`
- Rate plans: `getRatePlans(filter?)`, `getUpdatedRatePlans(filter?)`
- Charges: `getCharges(version, filter?)`, `getCharge(version, chargeIdOrKey)`
- Tiers: `getTiers(charge)`, `getTier(charge, tierIndexOrKey)`
- Quote fields: `getQuote()`, `getQuoteField(fieldName)`

Do not manually traverse `product.ratePlans`, `ratePlan.charges`, `quoteState.quoteRatePlans`, or `quoteState.quote` when a documented helper covers the read. Do not read quote header fields from `this.quoteState.quote`; use `getQuote()` or `getQuoteField(...)`.

## Rules

- Treat state as CPQ-owned. Do not directly mutate `quoteState`.
- Do not call `this.quoteState.getQuote()`, `this.quoteState.updateQuote(...)`, `connectedQuote.updateQuote(...)`, or resolver-style hook callbacks such as `resolve()`/`reject()`. Do not declare `@api record` for headless hooks, do not generate hook parameters such as `{ record, connectedQuote }`, and do not return `{ success: true }`. Use documented hook return values and, for package version 10.58 or later, `ZQFClient` helpers.
- Prefer documented helper methods first. Use manual traversal or custom logic only when no documented helper covers the requirement, and keep that fallback tied to documented public state or hook payloads.
- For Zuora managed package version 10.58 or later, use imported `ZQFClient` for quote state read, update, and fire/event operations. Do not generate raw public quote-state event construction in this path.
- For multiple CPQ object field updates in one hook, build one patch or grouped update and call the matching `ZQFClient` helper once for that object group. Reserve field-level helpers such as `updateQuoteField(...)`, `updateChargeField(...)`, and `updateTierField(...)` for exactly one field on one object.
- For ramp interval changes, use interval-aware helpers such as `getRampIntervals()` and `updateChargesInInterval(...)` with filter/update descriptors instead of selecting intervals through quote fields or manually traversing QRP/QRPC state.
- `quoteState.productTimelines` is an object map keyed by timeline ID, not an array. Use `this.zqf.getProductTimelines()` for array traversal.
- Ramp pricing and interval-scoped mutations iterate **ramp intervals** from `getRampIntervals()`, not **timeline versions** from `getVersions(...)`. Versions are effective-date slices within one timeline; ramp intervals are pricing periods across the quote.
- Do not use `RecordType.Name` to infer ramp quote behavior. Use ramp interval existence and, if provided, the real quote boolean ramp field being `true`.
- If the user states that `zqfClient` is available, treat the target as version 10.58 or later and use the `ZQFClient` import pattern.
- If the target package version is unknown and quote state helper behavior matters, ask the user to confirm whether the installed Zuora managed package version is 10.58 or later.
- If the target package version is earlier than 10.58, do not use `ZQFClient`; proceed with the generic public patterns below using supported hook return payloads and supported events from the catalog.
- Do not invent `ZQFClient` method names. Use only helper methods from `cpq-zqf-client.md` or the user's provided helper documentation.
- Do not rely on undocumented nested fields unless the field set or internal docs confirm availability.
- Starting in Quotes 10.50, `charge.originalQRPC` behavior changed; required fields must be included in `zqu__Original_QRPC` field set when referenced.

## Generic quote-state patterns for package versions earlier than 10.58

Use documented hook return payloads when the hook contract supports it. Product update hooks commonly return the updated payload plus `proceed: true`:

```js
@api
beforeProductUpdate(updatedCharges, updatedAmendment, updatedRatePlan, isRevert) {
  const nextCharges = updatedCharges.map((charge) => ({
    ...charge,
    quantity: Number(charge.quantity || 0)
  }));

  return {
    updatedCharges: nextCharges,
    updatedAmendment,
    updatedRatePlan,
    proceed: true
  };
}
```

Use supported events for quote-state actions. Register events that require Component Event Action setup.

```js
this.dispatchEvent(new CustomEvent('updateQuote', {
  detail: {
    quote: nextQuoteState
  }
}));

this.dispatchEvent(new CustomEvent('upsertQuoteLineItems', {
  detail: {
    quoteLineItems: nextQuoteLineItems
  }
}));

this.dispatchEvent(new CustomEvent('updateProducts', {
  detail: {
    productTimelines: nextProductTimelines
  }
}));

this.dispatchEvent(new CustomEvent('previewQuoteState'));
this.dispatchEvent(new CustomEvent('saveQuote'));
```
