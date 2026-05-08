---
name: zuora-review
description: Review work for Zuora best practices
argument-hint: [file path or description of what to review]
allowed-tools: [Read, Glob, Grep, Bash, Agent, mcp__zuora-mcp__zuora_codegen, mcp__zuora-mcp__ask_zuora, mcp__zuora-mcp__query_objects]
---

Codex-only path resolution: When an instruction refers to `${CLAUDE_PLUGIN_ROOT}`, treat it as the root of this installed plugin. In Codex, resolve that root as the ancestor directory containing `skills/`, `references/`, and `.codex-plugin/`.


You are reviewing Zuora-related implementation work for best practices, completeness, and correctness. This is broader than `/zuora-validate` — it evaluates the overall approach, not just individual code correctness.

## Input

What to review: $ARGUMENTS

## Workflow

### Step 1: Understand scope

Read the files or description. Determine what aspects to review:
- API integration code
- Workflow implementation
- Migration plan or scripts
- Product catalog setup
- Template/form design
- Overall architecture and approach

### Step 2: Gather Zuora context

Use MCP tools as needed:
- `mcp__zuora-mcp__ask_zuora` — for product-level best practices relevant to the implementation
- `mcp__zuora-mcp__zuora_codegen` with `code_rules` — for SDK-specific patterns
- `mcp__zuora-mcp__query_objects` — to check tenant state if relevant to the review

### Step 3: Read reference material

Read the relevant files from `${CLAUDE_PLUGIN_ROOT}/references/`:
- `best-practices.md` — always read for general Zuora best practices
- `api-integration-patterns.md` — for API integration reviews
- `workflow-patterns.md` — for workflow reviews
- `is-migration-patterns.md` — for IS migration reviews
- `order-migration-patterns.md` — for Order API migration reviews

### Step 4: Evaluate across dimensions

- **Correctness**: Do API calls use correct endpoints, fields, and enum values?
- **Completeness**: Are all required steps present (auth, error handling, pagination, cleanup)?
- **Robustness**: Error handling, retries, idempotency, rate limiting, STOP_AND_CONFIRM handling?
- **Performance**: Efficient API usage, appropriate batching, avoiding N+1 query patterns?
- **Security**: No hardcoded credentials, proper token management, secrets in environment variables?
- **Maintainability**: Clean structure, appropriate abstractions, configuration externalized?
- **Zuora-specific**: Following Zuora's recommended patterns for the specific use case?
- **Testing**: Is there a strategy for testing (sandbox, mocks, integration tests)?

### Step 5: Deliver the review

**Summary**: Overall assessment in 1-2 sentences

**Strengths**: What is done well (2-3 points)

**Issues** (prioritized by severity):
For each issue:
- Severity (critical / major / minor)
- Description
- Recommended fix

**Suggestions**: Non-blocking improvements for consideration

**Next steps**: What to do after addressing the review findings
