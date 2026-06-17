---
name: zuora-uat-design-worker
description: Internal SDD → TR matrix extraction (invoked by zuora-uat-design)
---

# SDD → TR matrix (internal)

Port of uat-test `analyze-sdd` adapted for `design/testmatrix/` layout.

## Filename rules

| `project_name` | Output |
|----------------|--------|
| Omitted | `{Feature}_TRs.md` |
| Set (e.g. `FW`) | `{project_name}_{System}_TRs.md` |

Incremental mode must use the same prefix as existing matrix files.

## TR scope presets

| Preset | max_trs_per_file | include_edge_cases |
|--------|------------------|-------------------|
| focused | 5 | off |
| standard | 10 | limited |
| comprehensive | 20 | on |

## Process

### Step 1: Discover SDDs

List `*.md` under `sdd_path`. Incremental: read only `target_sdd_file`.

### Step 2: Identify Zuora use cases

Categories: product catalog, subscriptions, billing/invoicing, payments, tax, usage, AR, revenue. One TR bullet per testable scenario.

### Step 3: Write matrix files

Format each TR as `- TR{n}: <summary>`. Group by feature/system. Enforce caps.

### Step 4: MCP helpers

- `mcp__zuora-mcp__zuora_codegen` — API endpoints and field names for TR wording
- `mcp__zuora-mcp__ask_zuora` — only if SDD scope needs product-behavior clarification after references

Do **not** use Avatar/PlayerZero tools.
