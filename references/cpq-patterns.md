# Zuora CPQ Customization Patterns

## Source Docs And Signatures

- Class names, method names, method parameters, return types, hook signatures, event names, event payload shapes, and Visualforce component attributes must strictly match official Zuora docs and examples bundled in this codebase.
- Do not invent helper classes, callback methods, overloads, event payload keys, or component attributes. If a signature is not documented locally or in the source docs, ask for the exact reference or state the assumption before generating code.
- Copy Quote Studio hook signatures exactly from `cpq-js-hooks.json`. Do not add resolver/reject parameters or host payload parameters such as `{ record, connectedQuote }`; `beforeSave`, `beforeSubmit`, and `beforePreviewCall` take no parameters and return optional Boolean values.
- Source docs:
  - https://docs.zuora.com/en/zuora-cpq/development-resources/zuora-cpq-component-library
  - https://docs.zuora.com/en/zuora-cpq/development-resources/overview-of-zuora-cpq-development-resources

## Quote Studio JavaScript

- Use headless components for save/submit/product lifecycle interception.
- Use sidebar components for visible UI assistance.
- Generate Quote Studio customizations as LWC classes extending `LightningElement` with public `@api` hook methods. Do not import `QuoteStudioHooks` from `@zuora/cpq`, extend `QuoteStudioHooks.ChargeFieldChange`, or generate `onInit`/`onChange` callbacks.
- Maintain one active headless component per Quote Studio configuration unless the user explicitly requests another component. Prefer the generic component name `headlessComponent`.
- For follow-up headless requirements, update the existing generic headless component instead of creating a new LWC. Consolidate hook and event logic into that component.
- If multiple existing headless components are found and the active component is ambiguous, ask the user which component to update before writing files.
- For non-MSQ headless components, include `@api quoteState`, `@api metricState`, and `@api pageState`.
- For MSQ headless components, include `@api quoteState`, `@api metricState`, `@api pageState`, `@api masterQuoteState`, and `@api parentQuoteState`.
- For Zuora managed package version 10.58 or later, or when the user states `zqfClient` is available, import `ZQFClient` from `zqu/zqfClient` and construct it from `quoteState` and `pageState` before reading, updating, or firing quote state changes.
- Do not call `this.quoteState.getQuote()`, `this.quoteState.updateQuote(...)`, `connectedQuote.updateQuote(...)`, or resolver-style hook callbacks. Do not declare `@api record` for headless hooks or return `{ success: true }`. Use `this.zqf.getQuote()`, `this.zqf.getQuoteField(...)`, and dispatched `this.zqf.updateQuote(patch)` events when ZQFClient is available.
- If the package version is unknown and the task requires quote state helper behavior, ask whether the installed Zuora managed package version is 10.58 or later.
- If the installed package version is earlier than 10.58, do not use `ZQFClient`; proceed with generic quote-state methods using supported hook return payloads and documented events from `cpq-js-events.json`.
- Use supported events to persist changes. Do not directly mutate CPQ-owned state and assume persistence.
- **Method selection priority**: (1) Use a documented ZQF helper from `cpq-zqf-client.md` first. (2) If no ZQF helper covers the requirement, fall back to generic patterns: hook return payloads, documented `quoteState` property reads, or raw `new CustomEvent(...)` with names from `cpq-js-events.json`; add a comment stating the assumption. (3) Never call a `this.zqf.*` method not listed in `cpq-zqf-client.md`, and never use raw `CustomEvent` for operations that have a ZQF mutation helper.
- Use `ZQFClient` mutation helpers instead of manually constructing quote-state update events when the target package version is 10.58 or later. Mutation helpers return `CustomEvent` objects; dispatch those returned events explicitly.
- For multiple CPQ object field updates in one hook, prefer the matching patch or bulk `ZQFClient` helper over repeated field-level helpers. Use `updateQuote(patch)` for quote fields, `updateCharges([...])` for QRPC charges, `updateRatePlans([...])` for QRP changes, `updateTiers([...])` for tiers, `updateAmendments([...])` for amendments, or `updateProducts({ ratePlans, charges, tiers })` for mixed product changes.
- For ramp interval charge updates, resolve the target interval with `getRampIntervals()`, `getActiveRampInterval()`, or `getRampIntervalByDate(...)` and use interval-scoped helpers such as `updateChargesInInterval(interval, updates)`. For second-ramp-interval QRPC updates, use the canonical `getRampIntervals()` plus `updateChargesInInterval(secondRampInterval, [{ filter, update }])` pattern from `cpq-zqf-client.md`. Use filter/update descriptors; do not select intervals with `getQuoteField(RAMP_INTERVAL_FIELD)`, manually traverse `getProducts()`, `product.ratePlans`, `ratePlan.charges`, `quoteState.quoteRatePlans`, `interval.charges`, or `secondInterval.charges`, and do not invent product/rate-plan-charge helpers.
- Do not detect ramp quotes by `RecordType.Name` or record type labels. For ramp-specific behavior, check whether ramp intervals exist and, when the real quote boolean field API name is known, whether that field is `true`.
- For product update hooks, return `{ proceed: true }` plus the updated payload keys required by the hook.
- For `toastMessageDisplay`, use `theme` values `warning`, `error`, or `success`.
- For `objectFieldConfig`, provide `field` and `object` and include timeline/charge context for charge-level configuration. Do not query or mutate Quote Studio DOM with `document.querySelector`, `[data-charge-id]`, `[data-field]`, or `.style.*`; use `objectfieldconfig` instead.
- Do not probe both namespaced and non-namespaced forms of the same field. Managed package fields use the `zqu__` namespace, for example `zqu__TriggerEvent__c`; custom fields outside the package do not use `zqu__`, for example `TriggerEvent__c`.

## Legacy Apex and Component Library

- Prefer global CPQ APIs over internal managed package classes.
- Keep namespace handling explicit: `zqu__Quote__c`, `zqu__QuoteRatePlan__c`, `zqu__QuoteRatePlanCharge__c`, and `zqu__QuoteAmendment__c`.
- Managed package fields and objects use the `zqu__` namespace. Custom fields and objects that are not part of the managed package must not use the `zqu__` namespace.
- Bulkify SOQL and DML.
- Keep Visualforce controllers thin and push reusable logic into Apex services.

## Migration

- Map legacy save/submit validation to `beforeSave` or `beforeSubmit`.
- Map legacy post-load UI behavior to `afterQuoteStudioLoad` plus supported events.
- Reimagine unsupported Visualforce/UI plugins as Quote Studio sidebar or headless components.
