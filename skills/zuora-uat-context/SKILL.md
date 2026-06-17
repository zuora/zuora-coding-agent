---
name: zuora-uat-context
description: Routes natural-language UAT/E2E test intent to zuora-uat slash commands. Use when the user mentions UAT tests, E2E test lifecycle, test matrix, TR files, test plan generation, API pytest, UI test docs, bridge-generate, or execute-full-test style workflows for Zuora.
version: 1.0.0
---

Codex-only path resolution: When an instruction refers to `${CLAUDE_PLUGIN_ROOT}`, treat it as the root of this installed plugin.

# Zuora UAT context router

## UAT workspace layout

UAT artifacts live under **`<git-root>/uat/`** by default (not repo root) to avoid collisions in mixed repos.

```
your-repo/
├── .zuora-uat.yaml       # root: uat
├── docs/sdd/             # SDDs at git root
└── uat/
    ├── design/
    └── execution/
```

Dedicated test repos: `root: .` in `.zuora-uat.yaml` or `UAT_ROOT=.`

## Registered commands

- `/zuora-uat-design` — `$zuora-uat-design`
- `/zuora-uat-build` — `$zuora-uat-build`
- `/zuora-uat-run` — `$zuora-uat-run`

## Command routing

| User intent | Command |
|---|---|
| Extract TRs from SDDs | `/zuora-uat-design` |
| Build plan + API + UI docs | `/zuora-uat-build` |
| Run API + UI tests | `/zuora-uat-run` |

## Typical chain

```
/zuora-uat-design
/zuora-uat-build features_input=<scope>
/zuora-uat-run features_input=<scope>
```

Read the matching top-level skill and follow it.

## References

Bundled under `${CLAUDE_PLUGIN_ROOT}/references/uat-test/`:

- `design/README.md` — UAT workspace layout
- `execution/docs/E2E_TEST_IMPLEMENTATION_GUIDELINE.md` — API test patterns
- `execution/docs/DEBUGGING_MECHANISM_GUIDE.md` — debug log format (`debug_utils.py`)
- `execution/docs/UI_TEST_DOC_FORMAT.md` / `UI_TEST_EXECUTION_GUIDELINE.md` — hybrid UI steps

## MCP

Use **zuora-mcp** (`zuora_codegen`, `ask_zuora`) per plugin tool-routing policy. UI execution also needs user-configured **Playwright MCP**.
