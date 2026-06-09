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

## Rules

- Treat state as CPQ-owned. Do not directly mutate `quoteState`.
- Do not call `this.quoteState.getQuote()`, `this.quoteState.updateQuote(...)`, `connectedQuote.updateQuote(...)`, or resolver-style hook callbacks such as `resolve()`/`reject()`. Do not declare `@api record` for headless hooks, do not generate hook parameters such as `{ record, connectedQuote }`, and do not return `{ success: true }`. Use documented hook return values and, for package version 10.58 or later, `ZQFClient` helpers.
- Prefer documented helper methods first. Use manual traversal or custom logic only when no documented helper covers the requirement, and keep that fallback tied to documented public state or hook payloads.
- For Zuora managed package version 10.58 or later, use imported `ZQFClient` for quote state read, update, and fire/event operations. Do not generate raw public quote-state event construction in this path.
- For multiple CPQ object field updates in one hook, build one patch or grouped update and call the matching `ZQFClient` helper once for that object group. Reserve field-level helpers such as `updateQuoteField(...)`, `updateChargeField(...)`, and `updateTierField(...)` for exactly one field on one object.
- For ramp interval changes, use interval-aware helpers such as `getRampIntervals()` and `updateChargesInInterval(...)` with filter/update descriptors instead of selecting intervals through quote fields or manually traversing QRP/QRPC state.
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
