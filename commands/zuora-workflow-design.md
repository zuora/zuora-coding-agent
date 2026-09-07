---
description: Design a Zuora Workflow (intent + plan artifacts via workflow-engine)
---

Run the `zuora-workflow-design` skill.

Produce `output/<name>.intent.json` and `output/<name>.plan.json`, validating each with:

```bash
${CLAUDE_PLUGIN_ROOT}/bin/workflow-engine validate-plan --stage intent -i ...
${CLAUDE_PLUGIN_ROOT}/bin/workflow-engine validate-plan --stage plan -i ...
```

Hand off the validated plan to `/zuora-workflow-build`.
