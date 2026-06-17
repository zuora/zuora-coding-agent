---
name: zuora-uat-generate-ui
description: Internal UI test doc generation for hybrid TRs
---

# Generate UI test doc (internal)

Creates `execution/tests/test_scenarios/test_<feature>/ui_steps_tr{n}.md` when the plan marks `UI Test Doc Required: Yes`.

**Never write** `ui_steps_tr{n}.md` under `design/testplan/` — that folder is design-only (plan overview + per-TR test design).

## Path resolution

Use `execution/tests/test_utils/repo_paths.py` from the customer repo (copy any missing files from `${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/tests/test_utils/`):

- `resolve_feature_scenario_dir(feature)` — target scenario directory
- `resolve_ui_steps_doc_path(feature, tr_index)` — final write path (raises if missing; use parent dir for writes)

Resolve the scenario directory before writing; output must land beside the API script for the same TR.

## Gap-fill

Skip when `force_overwrite=false` and `ui_steps_tr{n}.md` already exists at the resolved execution path (not under testplan).

## Format

Follow `${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/docs/UI_TEST_DOC_FORMAT.md`.

Include: prerequisites, debug log variable references, numbered UI steps, expected outcomes.

## MCP

`mcp__zuora-mcp__ask_zuora` for UI navigation paths when not in the test design. No Playwright during generation.
