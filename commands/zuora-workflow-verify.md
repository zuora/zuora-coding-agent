---
description: Import a lint-clean workflow to sandbox, test-run via MCP, and fix issues in a bounded loop
---

Run the `zuora-workflow-verify` skill.

Requires a lint-clean `.workflow.json`, matching `.plan.json`, and MCP access to the target sandbox tenant.

**You will be asked to confirm** before any import or test run (including fix-loop retries). Options: proceed (import + run), import only, or cancel.

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/lint-workflow-json.js output/<name>.workflow.json
```

Then import → `run_workflow` → poll `get_run_status` → fix plan → rebuild → relint → retry (default max 3 attempts).

For **event-triggered BATCH** workflows, the skill auto-discovers event context via `query_objects`, adds mirror `input_fields` to the plan when needed, and passes discovered ids at run time. Event-only (`REALTIME`/`UIACTION`) workflows stop at import/lint unless redesigned for testing.
