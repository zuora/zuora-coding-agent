---
name: zuora-uat-run
description: Execute API pytest and UI tests for scoped features with mark-driven verify gate
argument-hint: "[features_input=all] [environment=mcp] [verify=auto] [max_fix_retries=3]"
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash, Agent, Task, mcp__zuora-mcp__zuora_codegen, mcp__zuora-mcp__ask_zuora]
---

Codex-only path resolution: When an instruction refers to `${CLAUDE_PLUGIN_ROOT}`, treat it as the root of this installed plugin.

Orchestrator: discover scope → one worker per feature → aggregate.

## Input

$ARGUMENTS

| Parameter | Default |
|-----------|---------|
| `verify` | `auto` |
| `environment` | `mcp` |

## Workflow

### Step 1: Resolve UAT workspace

```bash
GIT_ROOT=$(git rev-parse --show-toplevel)
UAT_ROOT=$(python3 "${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/scripts/resolve_uat_root.py" \
  --git-root "$GIT_ROOT" | python3 -c "import sys,json; print(json.load(sys.stdin)['uat_root'])")
```

Resolve tenant:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/scripts/tenant_resolve.py" \
  --git-root "$GIT_ROOT" --environment mcp --scaffold-local
```

### Step 2: Discover scope

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/scripts/discover_groups.py" \
  --git-root "$GIT_ROOT" --features-input "<features_input>"
```

### Step 3: Delegate per feature

Pass `UAT_ROOT` to `${CLAUDE_PLUGIN_ROOT}/skills/zuora-uat/run-feature/SKILL.md` workers.

Each worker runs `ensure-manifest` at startup (see `run-feature/SKILL.md`).

### Step 4: Aggregate

Roll-up per TR; reports under `$UAT_ROOT/execution/reports/`.

## MCP

Use `mcp__zuora-mcp__zuora_codegen` during verify/fix. Call `mcp__zuora-mcp__ask_zuora` only for unresolved UI or billing-behavior questions.

## References

- `${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/docs/DEBUGGING_MECHANISM_GUIDE.md`
- `${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/docs/UI_TEST_EXECUTION_GUIDELINE.md`
