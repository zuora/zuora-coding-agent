# ZQFClient

`ZQFClient` is available in Zuora managed package version 10.58 and later. It is a customer-facing helper for Quote Studio extensibility code. It wraps quote-state traversal and common event construction.

## Selection rule

- If the user states the installed package version is 10.58 or later, or states that `zqfClient` is available, use `ZQFClient`.
- Do not manually construct quote-state events with `new CustomEvent('updateQuote' | 'upsertQuoteLineItems' | 'updateProducts' | 'previewQuoteState' | 'saveQuote')` in the 10.58-or-later path.
- If the installed package version is earlier than 10.58, do not use `ZQFClient`; use the generic public event and hook-return examples in `cpq-js-state-model.md`.
- If the package version is unknown and the requirement needs quote-state read/update/fire behavior, ask the user to confirm whether the installed package is 10.58 or later.

## Import and client construction

Use the module import. Do not declare `@api zqfClient`.

```js
import { LightningElement, api } from 'lwc';
import ZQFClient from 'zqu/zqfClient';

export default class HeadlessComponent extends LightningElement {
  @api quoteState;
  @api metricState;
  @api pageState;

  get zqf() {
    return ZQFClient.from(() => this.quoteState, {
      pageState: () => this.pageState
    });
  }
}
```

Forbidden patterns:

- `@api zqfClient`
- `@api record`
- `this.zqfClient`
- `this.zqfClient.hooks.register(...)`
- `connectedCallback()` registration for Quote Studio hooks
- resolver-style hook parameters such as `beforeSave({ resolve, reject })`
- host-payload hook parameters such as `beforeSave({ record, connectedQuote })`
- `resolve()` / `reject()` callback completion inside hooks
- `connectedQuote.updateQuote(...)`
- `return { success: true }`
- `this.quoteState.getQuote()`
- `this.quoteState.updateQuote(...)`
- `this.quoteState.setFieldValue(...)`

Quote Studio hook methods are declared directly as public `@api` methods such as `beforeSave()`, `beforeSubmit()`, and `afterProductAdd(addedProducts)`. Copy the exact hook signature from `cpq-js-hooks.json`; do not add extra parameters. `beforeSave`, `beforeSubmit`, and `beforePreviewCall` take no parameters and return optional Boolean values.

For MSQ, also include:

```js
@api masterQuoteState;
@api parentQuoteState;
```

## Field names

- Standard Salesforce fields stay unnamespaced, for example `Id` and `Name`.
- Zuora package fields must use the full namespace, for example `zqu__Quantity__c` and `zqu__ContractEffectiveDate__c`.
- Custom fields outside the Zuora managed package must not use the `zqu__` namespace.

## Read helpers

Use these methods to inspect quote state without manual traversal:

- Quote: `getQuote()`, `getQuoteField(fieldName)`, `getSubscription()`.
- Product timelines: `getProductTimelines(filter?)`, `getTimeline(timelineId)`, `getVersions(timelineId, filter?)`.
- Rate plans: `getRatePlans(filter?)`, `getRatePlansByAmendmentType(type, filter?)`, `getUpdatedRatePlans(filter?)`, `getRemovedRatePlans(filter?)`, `getOriginalRatePlans(filter?)`.
- Versions: `getLatestVersion(timelineId, filter?)`, `getVersionByEffectiveDate(timelineId, effectiveDate, filter?)`.
- Charges and tiers: `getCharges(version, filter?)`, `getCharge(version, chargeIdOrKey)`, `getTiers(charge)`, `getTier(charge, tierIndexOrKey)`.
- Ramp intervals: `getRampIntervals()`, `getActiveRampInterval()`, `getRampIntervalByDate(date)`.
- Amendments: `getAmendments(filter?)`, `getAmendment(timelineIdOrFilter, filter?)`, `getAmendmentRecord(amendment)`, `getAmendmentType(version)`.

Example:

```js
const quote = this.zqf.getQuote();
const term = this.zqf.getQuoteField('zqu__InitialTerm__c');
const updatedPlans = this.zqf.getRatePlans({ type: 'UpdateProduct' });
```

Do not read from `this.quoteState.getQuote()`; use `this.zqf.getQuote()` or `this.zqf.getQuoteField(fieldName)` when ZQFClient is available.

Unsupported invented helpers:

- Do not generate `getProducts(...)`; use documented read helpers such as `getProductTimelines(...)`, `getRatePlans(...)`, `getVersions(...)`, and `getCharges(...)` for reads, and prefer mutation helper filters for updates.
- Do not generate `getRatePlanField(...)`; read `ratePlan.record.<FieldApiName>` in filters or after `getRatePlans(...)`.
- Do not generate `getRatePlanCharges(...)`; use `getVersions(...)` plus `getCharges(version, filter?)` for explicit reads, or prefer mutation helper filters for updates.
- Do not generate `getRatePlanChargeField(...)`; read `charge.record.<FieldApiName>`.
- Do not generate `updateRatePlanCharges(...)`; use `updateCharges(...)`, `updateChargesInInterval(...)`, or `updateProducts({ charges })`.

## Mutation helpers

Mutation helpers return `CustomEvent` objects. Hook code must dispatch the returned event explicitly.

Quote helpers:

- `updateQuote(patch?)`
- `updateQuoteField(fieldName, value)`

Do not call `this.quoteState.updateQuote(...)`; dispatch `this.zqf.updateQuote(patch)` or `this.zqf.updateQuoteField(fieldName, value)` when ZQFClient is available.

Bulk state-update rule:

- Use field-level helpers only for one field on one object. This includes `updateQuoteField(...)`, `updateChargeField(...)`, `updateChargeFieldInInterval(...)`, `updateTierField(...)`, and `updateTierFieldInInterval(...)`.
- For two or more quote fields, build one patch and dispatch `updateQuote(patch)`.
- For two or more QRPC charge fields on one charge, use `updateCharge(..., patch)` or `updateChargeInInterval(..., patch)`. For multiple charges, use `updateCharges([...])` or `updateChargesInInterval(...)`.
- `updateCharges(...)` and `updateChargesInInterval(...)` bulk entries should use the documented descriptor shape `{ filter: (charge, ratePlan, timeline, context) => boolean, update: { ...fields } }`.
- Do not generate `updateCharges(...)` or `updateChargesInInterval(interval, chargeUpdates)` where `chargeUpdates` was manually built by traversing `getProducts()`, `product.ratePlans`, `ratePlan.charges`, `quoteState.quoteRatePlans`, `interval.charges`, or `secondInterval.charges` into `{ id, chargeId, ...fields }` records. Prefer filter descriptors; the helper supplies the parent rate plan to the filter callback.
- For tier field changes, use `updateTier(..., patch)`, `updateTierInInterval(..., patch)`, `updateTiers([...])`, or `updateTiersInInterval(...)` instead of repeated tier field helpers.
- For QRP, amendment, product, or mixed QRP/QRPC/tier changes, use the collection helpers such as `updateRatePlans([...])`, `updateAmendments([...])`, `updateProducts({ ratePlans, charges, tiers })`, or their interval variants.
- Do not dispatch multiple field-level update events for related CPQ object changes; one patch or grouped bulk update keeps the mutation atomic and easier to validate.

Product add helpers:

- `addProducts(productIds, options?)`
- `addProductsInInterval(intervalId, productIds, options?)`

Charge helpers:

- `addCharge(timelineId, chargeInput)`
- `addChargeInInterval(intervalId, timelineId, chargeInput)`
- `updateCharge(timelineId, chargeIdOrKey, patch)`
- `updateChargeInInterval(intervalId, timelineId, chargeIdOrKey, patch)`
- `updateChargeField(timelineId, chargeIdOrKey, fieldName, value)`
- `updateChargeFieldInInterval(intervalId, timelineId, chargeIdOrKey, fieldName, value)`
- `removeCharge(timelineId, chargeIdOrKey)`
- `removeChargeInInterval(intervalId, timelineId, chargeIdOrKey)`

Tier helpers:

- `updateTier(timelineId, chargeIdOrKey, tierIndexOrKey, patch)`
- `updateTierInInterval(intervalId, timelineId, chargeIdOrKey, tierIndexOrKey, patch)`
- `updateTierField(timelineId, chargeIdOrKey, tierIndexOrKey, fieldName, value)`
- `updateTierFieldInInterval(intervalId, timelineId, chargeIdOrKey, tierIndexOrKey, fieldName, value)`

Product helpers:

- `updateProduct(timelineId, options?)`
- `updateProductInInterval(intervalId, timelineId, options?)`
- `removeProducts(removals)`
- `removeProductsInInterval(intervalId, removals)`
- `removeProduct(timelineId)`
- `removeProductInInterval(intervalId, timelineId)`

Bulk update helpers:

- `updateCharges(updates)`
- `updateChargesInInterval(intervalId, updates)`
- `updateRatePlans(updates)`
- `updateRatePlansInInterval(intervalId, updates)`
- `updateAmendments(updates)`
- `updateAmendmentsInInterval(intervalId, updates)`
- `updateTiers(updates)`
- `updateTiersInInterval(intervalId, updates)`
- `updateProducts(groups?)`
- `updateProductsInInterval(intervalId, groups?)`

Return events:

- `addProducts` and `addProductsInInterval` return `CustomEvent('addproducts')`.
- Quote updates return `CustomEvent('updatequote')`.
- Other mutations return `CustomEvent('updateproducts')`.

## Examples

Update quote fields:

```js
const quotePatch = {};

if (this.zqf.getQuoteField('Name') !== 'Updated Quote Name') {
  quotePatch.Name = 'Updated Quote Name';
}

if (this.zqf.getQuoteField('zqu__Billing_Region__c') !== 'EMEA') {
  quotePatch.zqu__Billing_Region__c = 'EMEA';
}

if (Object.keys(quotePatch).length > 0) {
  this.dispatchEvent(this.zqf.updateQuote(quotePatch));
}
```

Single quote field update:

```js
this.dispatchEvent(
  this.zqf.updateQuoteField('zqu__Billing_Region__c', 'EMEA')
);
```

Add products:

```js
this.dispatchEvent(
  this.zqf.addProducts(['a0hEi00000CRApNIAX', 'a0hEi00000CRApKIAX'], {
    effectiveDate: '2026-07-13'
  })
);
```

Update charges by rate plan:

```js
this.dispatchEvent(
  this.zqf.updateCharges([
    {
      filter: (charge, plan) => plan.record.Name === 'JIO',
      update: {
        zqu__Discount__c: 25,
        zqu__Quantity__c: 12
      }
    },
    {
      filter: (charge, plan) => plan.record.Name === 'Airtel',
      update: {
        zqu__Discount__c: 15,
        zqu__Quantity__c: 10
      }
    }
  ])
);
```

Update rate plans, charges, and tiers together:

```js
this.dispatchEvent(
  this.zqf.updateProducts({
    charges: [
      {
        filter: (charge) => charge.record.Name === 'Per MB Charge',
        update: {
          zqu__Discount__c: 22
        }
      }
    ],
    tiers: [
      {
        filter: (tier, charge) =>
          charge.record.Name === 'Recurring Charges -3Tier' &&
          tier.record.zqu__StartingUnit__c === 0 &&
          tier.record.zqu__EndingUnit__c === 50,
        update: {
          zqu__Discount__c: 5
        }
      }
    ],
    ratePlans: []
  })
);
```

Update discount in a selected interval. The interval argument can be an interval index, interval id, interval start date, or interval object.

```js
this.dispatchEvent(
  this.zqf.updateChargesInInterval(2, [
    {
      filter: (charge) => charge.record.Name === 'Per MB Charge',
      update: {
        zqu__Discount__c: 20
      }
    }
  ])
);
```

Canonical second-ramp-interval QRPC update by rate plan:

```js
const rampIntervals = this.zqf.getRampIntervals() || [];
const secondRampInterval = rampIntervals[SECOND_RAMP_INTERVAL_INDEX];

if (!secondRampInterval) {
  return;
}

this.dispatchEvent(
  this.zqf.updateChargesInInterval(secondRampInterval, [
    {
      filter: (charge, ratePlan) =>
        ratePlan?.record?.Name === AIRTEL_RATE_PLAN_NAME,
      update: {
        zqu__Quantity__c: 100,
        zqu__Discount__c: 11
      }
    },
    {
      filter: (charge, ratePlan) =>
        ratePlan?.record?.Name === JIO_RATE_PLAN_NAME,
      update: {
        zqu__Discount__c: 22
      }
    }
  ])
);
```

Ramp quote detection:

```js
const rampIntervals = this.zqf.getRampIntervals() || [];
const isRampQuote =
  rampIntervals.length > 0 ||
  this.zqf.getQuoteField(IS_RAMP_QUOTE_FIELD) === true;
```

Use the actual quote boolean field API name for `IS_RAMP_QUOTE_FIELD` when it is known. If the field API name is not known, rely on ramp interval existence for ramp-interval logic or ask for the field API name. Do not use `this.zqf.getQuoteField('RecordType.Name') === RAMP_RECORD_TYPE`; record type labels are not a reliable ramp-state API.

Do not select the active or second ramp interval using `this.zqf.getQuoteField(RAMP_INTERVAL_FIELD)`. Use `getRampIntervals()` and select the interval object, or use `getActiveRampInterval()` / `getRampIntervalByDate(...)` when those match the requirement.

Avoid this manual traversal shape for ramp interval QRPC updates:

```js
// WRONG — do not generate this pattern
const rampInterval = this.zqf.getQuoteField(RAMP_INTERVAL_FIELD); // wrong: interval must come from getRampIntervals()
const products = this.zqf.getProducts(); // wrong: getProducts() does not exist
const chargesToUpdate = [];

for (const product of products) {
  for (const ratePlan of product.ratePlans || []) {
    const ratePlanName = ratePlan[RATE_PLAN_NAME_FIELD]; // wrong: must use ratePlan?.record?.Name

    for (const charge of ratePlan.charges || []) {
      chargesToUpdate.push({
        chargeId: charge.id, // wrong: do not precompute id-based payloads
        zqu__Discount__c: 22
      });
    }
  }
}

this.dispatchEvent(this.zqf.updateCharges(chargesToUpdate)); // wrong: must use updateChargesInInterval for interval-scoped logic
```

Also avoid the map variant:

```js
// WRONG — do not generate this pattern
const chargeUpdates = secondInterval.charges.map((charge) => ({
  chargeId: charge.id,
  zqu__Discount__c: 22
}));

this.dispatchEvent(this.zqf.updateCharges(chargeUpdates));
```

The filter/update descriptor is preferred because `updateChargesInInterval` already evaluates charges in the selected interval and passes the parent rate plan into the filter callback.

## Field styling and configuration

For field-level styling (backgroundColor, readOnly, helptext), use the `objectfieldconfig` CustomEvent. There is no ZQF helper for this; construct the event directly. See Zuora KC for field config options.

```js
// CORRECT — use objectFieldConfig for field styling
this.dispatchEvent(
  new CustomEvent("objectfieldconfig", {
    detail: {
      configs: [{
        field: "zqu__Discount__c",
        object: "QuoteRatePlanCharge",
        chargeIndex: 0,
        timelineId: "timeline-123",
        effectiveDate: "2024-01-01",
        backgroundColor: quantity > 10 ? "#FFA500" : "#FFFFFF",
        readOnly: quantity > 10,
        helptext: quantity > 10 ? "Discount locked" : ""
      }]
    }
  })
);
```

Forbidden patterns:

```js
// WRONG — do not use updateMetricState for field styling
this.dispatchEvent(
  this.zqf.updateMetricState({        // does not exist
    styling: { [fieldPath]: { backgroundColor: "#FFA500" } }
  })
);

// WRONG — do not use this.zqf.objectFieldConfig, it does not exist
this.dispatchEvent(this.zqf.objectFieldConfig(config));

// WRONG — do not use this.zqf.setField for field styling
this.zqf.setField(chargeId, 'Quantity', { readOnly: true });

// WRONG — do not style Quote Studio DOM directly
document.querySelector('[data-charge-id="..."] input').style.backgroundColor = 'orange';
```

Source docs:
- https://docs.zuora.com/en/zuora-cpq/development-resources/zuora-cpq-component-library
- https://docs.zuora.com/en/zuora-cpq/development-resources/overview-of-zuora-cpq-development-resources
