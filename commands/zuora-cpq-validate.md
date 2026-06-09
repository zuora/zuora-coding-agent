---
description: Validate Zuora CPQ Apex, Visualforce, or Quote Studio JavaScript customization code.
---

# /zuora-cpq-validate

Read `${CLAUDE_PLUGIN_ROOT}/skills/zuora-cpq-validate/SKILL.md` and follow it for this request:

```text
$ARGUMENTS
```

For Quote Studio JavaScript, run `${CLAUDE_PLUGIN_ROOT}/scripts/lint-cpq-hooks-events.js` when files are available. Treat these patterns as invalid: `beforeSave({ quoteState, zqfClient })`, `beforeSave({ resolve, reject })`, `beforeSave({ record, connectedQuote })`, injected `zqfClient`, `quoteState.getQuote()`, `quoteState.setQuoteField(...)`, `return { success: true }`, and CPQ hooks/targets in LWC `*-meta.xml`.
