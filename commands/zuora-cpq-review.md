---
description: Review Zuora CPQ customization code for correctness, maintainability, and best practices.
---

# /zuora-cpq-review

Read `${CLAUDE_PLUGIN_ROOT}/skills/zuora-cpq-review/SKILL.md` and follow it for this request:

```text
$ARGUMENTS
```

For Quote Studio JavaScript, flag incorrect hook signatures, injected `zqfClient`, host payloads, resolver callbacks, `quoteState.getQuote()`, `quoteState.setQuoteField(...)`, `return { success: true }`, direct Quote Studio DOM styling, invented ZQF helpers, and CPQ hooks/targets in LWC `*-meta.xml`.
