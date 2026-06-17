---
name: zuora-uat-build
description: Build test plan, API scripts, and UI docs for scoped features; optional verify segment
argument-hint: "[features_input=all] [force_overwrite=false] [verify=false] [environment=mcp] [max_fix_retries=3]"
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash, Agent, Task, mcp__zuora-mcp__zuora_codegen, mcp__zuora-mcp__ask_zuora]
---

Codex-only path resolution: When an instruction refers to `${CLAUDE_PLUGIN_ROOT}`, treat it as the root of this installed plugin.

Orchestrator: discover scope → one worker per feature → aggregate. **Does not run pytest by default** (`verify=false`).

## Input

$ARGUMENTS

## Workflow

### Step 1: Resolve paths and scaffold

```bash
GIT_ROOT=$(git rev-parse --show-toplevel)
UAT_ROOT=$(python3 "${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/scripts/resolve_uat_root.py" \
  --git-root "$GIT_ROOT" | python3 -c "import sys,json; print(json.load(sys.stdin)['uat_root'])")
```

If `$UAT_ROOT/design` missing, scaffold per `zuora-uat-design` Step 2.

### Step 2: Discover scope

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/scripts/discover_groups.py" \
  --git-root "$GIT_ROOT" \
  --features-input "<features_input>"
```

### Step 3: Delegate per feature

Pass workers: feature stem, `tr_filter`, flags, `UAT_ROOT`, and `${CLAUDE_PLUGIN_ROOT}/skills/zuora-uat/generate-feature/SKILL.md`.

**Multiple features:** sequential sub-agents. **Single feature:** inline OK.

Collect **compact JSON summary only** from workers.

### Step 3b: Finalize verification marks (required)

After each feature worker completes, **always** run (do not skip even if the worker JSON already lists verification):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/scripts/uat_verification.py" finalize-generate \
  --git-root "$GIT_ROOT" \
  --feature "<feature_stem>" \
  --verify "<verify>"
# When the worker had tr_filter, append --tr N for each TR in scope
```

When `verify=false`, this writes `{"verified": false}` for every TR in scope to `.uat-verification.json`. When `verify=true`, this is a no-op (the verify segment sets marks on pass/fail).

Validate the manifest (must pass before continuing):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/scripts/uat_verification.py" validate \
  --scenario-dir "$UAT_ROOT/execution/tests/test_scenarios/<scenario_folder>"
```

If validate fails, re-run `ensure-manifest` for that feature and report the failure in the roll-up.

### Step 4: Aggregate

Roll-up table per feature. One failure does not abort siblings.

## MCP

Use `mcp__zuora-mcp__zuora_codegen` during generation. Call `mcp__zuora-mcp__ask_zuora` only when verify/fix needs unresolved product-behavior answers.

## References

- `${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/docs/E2E_TEST_IMPLEMENTATION_GUIDELINE.md`
- `${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/docs/UI_TEST_DOC_FORMAT.md`
