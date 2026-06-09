---
description: Generate Zuora CPQ Quote Studio or CPQ X LWC headless/sidebar components in a Salesforce DX repo.
---

# /zuora-cpq-js-build

Read `${CLAUDE_PLUGIN_ROOT}/skills/zuora-cpq-js-build/SKILL.md` and follow it for this request:

```text
$ARGUMENTS
```

Critical Quote Studio rules:

- Copy hook signatures exactly from `${CLAUDE_PLUGIN_ROOT}/references/cpq-js-hooks.json`.
- `beforeSave`, `beforeSubmit`, and `beforePreviewCall` take no parameters and return optional Boolean values.
- Never generate `beforeSave({ quoteState, zqfClient })`, `beforeSave({ resolve, reject })`, `beforeSave({ record, connectedQuote })`, `resolve()`, `reject()`, `connectedQuote.updateQuote(...)`, or `return { success: true }`.
- For package 10.58 or later, import `ZQFClient` from `zqu/zqfClient`, construct it from `this.quoteState` and `this.pageState`, and dispatch events returned by documented helpers.
- Do not generate `@api zqfClient`, `@api record`, `@api recordId`, `this.zqfClient`, bare `zqfClient`, `quoteState.getQuote()`, `quoteState.setQuoteField(...)`, `this.quoteState.getQuote()`, `this.quoteState.updateQuote(...)`, or `this.quoteState.setFieldValue(...)`.
- Do not add CPQ hooks, targets, target configs, or hook entries to LWC `*-meta.xml`.
