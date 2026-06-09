---
description: Design Zuora CPQ Quote Studio JavaScript extensibility using supported hooks and events.
---

# /zuora-cpq-js-design

Read `${CLAUDE_PLUGIN_ROOT}/skills/zuora-cpq-js-design/SKILL.md` and follow it for this request:

```text
$ARGUMENTS
```

Critical Quote Studio rules:

- Copy hook signatures exactly from `${CLAUDE_PLUGIN_ROOT}/references/cpq-js-hooks.json`.
- `beforeSave`, `beforeSubmit`, and `beforePreviewCall` take no parameters and return optional Boolean values.
- Never design `beforeSave({ quoteState, zqfClient })`, `beforeSave({ resolve, reject })`, `beforeSave({ record, connectedQuote })`, `resolve()`, `reject()`, `connectedQuote.updateQuote(...)`, or `return { success: true }`.
- For package 10.58 or later, use the `ZQFClient` module import pattern, not injected or hook-parameter `zqfClient`.
- Do not design `@api zqfClient`, `@api record`, `@api recordId`, `this.zqfClient`, bare `zqfClient`, `quoteState.getQuote()`, `quoteState.setQuoteField(...)`, `this.quoteState.getQuote()`, `this.quoteState.updateQuote(...)`, or `this.quoteState.setFieldValue(...)`.
- Do not put CPQ hook/event registration into LWC `*-meta.xml`.
