---
description: Build importable Zuora Workflow JSON from a validated plan
---

Run the `zuora-workflow-build` skill.

Build only via the engine:

```bash
${CLAUDE_PLUGIN_ROOT}/bin/workflow-engine build -i <plan>.plan.json -o output/<name>.workflow.json
node ${CLAUDE_PLUGIN_ROOT}/scripts/lint-workflow-json.js output/<name>.workflow.json
```

When lint passes and the user wants sandbox validation, continue with `/zuora-workflow-verify`.
