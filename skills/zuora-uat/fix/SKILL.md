---
name: zuora-uat-fix
description: Internal fix loop for failing API or UI tests
---

# Fix test implementation (internal)

Analyze failures and fix `test_*_tr{n}_api.py` and/or `ui_steps_tr{n}.md`.

## Process

### Step 1: Identify failure source

Check `execution/debugging/` logs and `execution/reports/` for API/UI outcomes.

### Step 2: Classify root cause

API bug, test design issue, UI doc issue, missing debug IDs, or external service issue (do not mask service bugs).

### Step 3: Apply fix

- API: edit Python test; re-run pytest
- UI: edit `ui_steps_tr{n}.md`; ensure debug log captures required variables
- Use `mcp__zuora-mcp__zuora_codegen` for API corrections; search repo for patterns

### Step 4: Clear verification mark

After editing artifacts, set `verified: false`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/scripts/uat_verification.py" clear \
  --scenario-dir "<scenario_dir>" --tr <n>
```

Retry up to `max_fix_retries`.
