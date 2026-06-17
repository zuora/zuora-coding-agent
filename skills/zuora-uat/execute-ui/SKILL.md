---
name: zuora-uat-execute-ui
description: Internal UI test execution via Playwright MCP
---

# Execute UI test (internal)

## Entry

Prefer starting from `hybrid_tr_prepare.py` output (called by `run-feature` after API pytest passes):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/scripts/hybrid_tr_prepare.py" \
  --git-root "$GIT_ROOT" \
  --feature "<feature>" \
  --tr <n> \
  --environment "<environment>"
```

When `execute_ui` is `true`, proceed. Otherwise stop and return the `skip_reason`.

Manual fallback for debug variables:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/scripts/parse_debug_variables.py" \
  --git-root "$GIT_ROOT" \
  --feature "<feature>" \
  --tr <n>
```

## Preconditions

Skip UI with a clear message when **any** of:

- `hybrid_tr_prepare.py` returns `execute_ui: false`
- Playwright MCP unavailable
- API pytest failed for this TR (`api_test_passed: false`)

## Process

1. Use `variables` from `hybrid_tr_prepare.py` (or `parse_debug_variables.py`) — do not hand-parse debug logs unless scripts fail
2. Read `ui_steps_path` / `ui_steps_tr{n}.md`
3. Execute steps via Playwright MCP tools
4. Write report to `execution/reports/`
5. Capture evidence paths for `record-ui-result`

Follow `${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/docs/UI_TEST_EXECUTION_GUIDELINE.md`.

## MCP

Use user-configured Playwright MCP (not bundled). `mcp__zuora-mcp__ask_zuora` for unresolved UI behavior only.
