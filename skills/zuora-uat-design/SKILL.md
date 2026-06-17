---
name: zuora-uat-design
description: Extract test requirements from SDDs into design/testmatrix/ TR files for the zuora-uat lifecycle
argument-hint: "[project_name=<label>] [sdd_path=docs/sdd/] [analysis_mode=full|incremental] [tr_scope=focused|standard|comprehensive]"
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash, Agent, mcp__zuora-mcp__zuora_codegen, mcp__zuora-mcp__ask_zuora]
---

Codex-only path resolution: When an instruction refers to `${CLAUDE_PLUGIN_ROOT}`, treat it as the root of this installed plugin.

Extract Zuora Billing use cases from SDDs into `<uat-root>/design/testmatrix/`. **No tenant access.**

## Input

$ARGUMENTS

| Parameter | Default | Notes |
|-----------|---------|-------|
| `project_name` | *(omit)* | When set, `{project}_{System}_TRs.md`. When omitted, `{Feature}_TRs.md` |
| `sdd_path` | `docs/sdd/` | Relative to **git root** (not `uat/`) |
| `analysis_mode` | `full` | `incremental` requires `target_sdd_file` |
| `tr_scope` | `focused` | TR count caps |

## Workflow

### Step 1: Resolve UAT workspace

```bash
GIT_ROOT=$(git rev-parse --show-toplevel)
UAT_ROOT=$(python3 "${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/scripts/resolve_uat_root.py" \
  --git-root "$GIT_ROOT" | python3 -c "import sys,json; print(json.load(sys.stdin)['uat_root'])")
```

Default UAT root: `$GIT_ROOT/uat/`. Override with `UAT_ROOT` or `.zuora-uat.yaml` (`root: .` for dedicated test repos).

### Step 2: Scaffold if needed

If `$UAT_ROOT/design/testmatrix/` is missing:

```bash
mkdir -p "$GIT_ROOT/uat"
cp -r "${CLAUDE_PLUGIN_ROOT}/templates/uat-test-starter/uat/"* "$GIT_ROOT/uat/"
cp "${CLAUDE_PLUGIN_ROOT}/templates/uat-test-starter/.zuora-uat.yaml" "$GIT_ROOT/.zuora-uat.yaml"
```

### Step 3: Run design extraction

Read `${CLAUDE_PLUGIN_ROOT}/skills/zuora-uat/design/SKILL.md`. Write TR files under `$UAT_ROOT/design/testmatrix/`.

### Step 4: Summarize

Report UAT root, files written, TR counts, caps applied.

## References

- `${CLAUDE_PLUGIN_ROOT}/references/uat-test/design/README.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/zuora-uat/design/SKILL.md`

## MCP substitution

Use `mcp__zuora-mcp__zuora_codegen` for API specs; `mcp__zuora-mcp__ask_zuora` only for unresolved product-behavior questions.
