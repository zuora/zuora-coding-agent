---
name: zuora-uat-plan
description: Internal create-test-plan step (gap-fill per TR design files)
---

# Create test plan (internal)

Creates `design/testplan/<Feature>_Test_Plan/` with `Test_Plan_Overview.md` + `tr{n}_test_design.md`.

**Design-only boundary:** `design/testplan/` must contain only plan documents. Never create `ui_steps_tr{n}.md` or API test scripts there — those are execution artifacts under `execution/tests/test_scenarios/test_<feature>/`.

## Gap-fill

When `force_overwrite=false`, only create **missing** `tr{n}_test_design.md`. Update overview links for new TRs.

## Path resolution

Use `execution/tests/test_utils/repo_paths.py` from the customer repo (copy any missing files from `${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/tests/test_utils/`):

- `resolve_feature_testplan_dir(feature)`
- `resolve_tr_test_design_path(feature, tr_index)`
- `testplan_overview_path(feature)`
- `resolve_feature_scenario_dir(feature)` — for execution-artifact paths in hybrid plan docs

## Writing rules

- Overview ≤120 lines: prerequisites, shared API refs, links to per-TR files
- Per-TR file ≤200 lines: Test ID, Summary, UI Test Doc Required (hybrid), Steps, Notes
- Hybrid TRs: mark `UI Test Doc Required: Yes`
- Hybrid TR cross-reference in `tr{n}_test_design.md`:
  - Use: `## UI steps (see execution/tests/test_scenarios/test_<feature>/ui_steps_tr{n}.md)`
  - Keep a short inline UI summary in the plan; the full Playwright doc belongs in execution
- `Test_Plan_Overview.md` for hybrid features must include:
  - `Execution artifacts: execution/tests/test_scenarios/test_<feature>/`
  - Artifacts table lists filenames only (e.g. `ui_steps_tr1.md`, `test_<feature>_tr1_api.py`)

## References

- `${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/docs/SHARED_STAGING_TENANT_POLICY.md`
- `${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/docs/E2E_TEST_IMPLEMENTATION_GUIDELINE.md`

## MCP

`mcp__zuora-mcp__zuora_codegen` for endpoint details; `mcp__zuora-mcp__ask_zuora` for unresolved UI/navigation questions.
