---
name: zuora-validate
description: Validate generated code, payloads, or approach against Zuora patterns
argument-hint: [file path or inline code/payload]
allowed-tools: [Read, Glob, Grep, Bash, Agent, mcp__zuora-mcp__zuora_codegen, mcp__zuora-mcp__ask_zuora, mcp__zuora-mcp__query_objects]
---

Codex-only path resolution: When an instruction refers to `${CLAUDE_PLUGIN_ROOT}`, treat it as the root of this installed plugin. In Codex, resolve that root as the ancestor directory containing `skills/`, `references/`, and `.codex-plugin/`.


You are validating Zuora-related code, API payloads, or design approaches against known Zuora patterns and best practices.

## Input

What to validate: $ARGUMENTS

## Tool routing

Use local file reads, bundled references, and `mcp__zuora-mcp__zuora_codegen` for structured validation of APIs, models, fields, enum values, SDK patterns, and payload shape. Use `mcp__zuora-mcp__ask_zuora` only when a concrete product-behavior or best-practice judgment remains after those checks.

## Workflow

### Step 1: Identify what to validate

Read the file or inline content the user provides. Determine the type:
- SDK integration code (Java, Python, Node.js, C#)
- curl commands or raw API payloads
- API design approach
- Workflow configuration
- Migration plan or scripts

### Step 2: Check against SDK rules

For code validation, call `mcp__zuora-mcp__zuora_codegen`:
- `code_rules` for the relevant language — get coding rules and patterns
- `get_model_details` for models used in the code — verify field names, types, and enum values are correct
- `get_api_details` for endpoints used — verify correct HTTP methods, required parameters, and request shapes

### Step 3: Check against best practices

Read `${CLAUDE_PLUGIN_ROOT}/references/best-practices.md` and check for:

- **Authentication**: Is OAuth token caching implemented? Are credentials hardcoded?
- **Error handling**: Are retries with exponential backoff implemented for transient failures (429, 5xx)?
- **Pagination**: Is cursor-based pagination used for list operations?
- **Idempotency**: Are create operations guarded with Idempotency-Key headers?
- **Rate limiting**: Is rate limit handling present?
- **Field correctness**: Are enum values and field names from actual SDK models (not guessed)?
- **Date formats**: Are dates in YYYY-MM-DD format?
- **Required fields**: Are all required fields populated?
- **Zuora-Version header**: Is it included and pinned to a known version?
- **STOP_AND_CONFIRM handling**: Are permanent error responses handled without retry?

### Step 4: Domain validation

Only call `mcp__zuora-mcp__ask_zuora` for a specific unresolved domain-level question about whether the approach is correct for the Zuora product area being used (Billing, Revenue, CPQ, Payments). The prompt must name the exact concern and summarize the codegen/reference checks already completed. Skip this step when structured validation is sufficient.

### Step 5: Report findings

Deliver a structured validation report:

**Status**: PASS / WARN / FAIL

**Issues found** (if any):
For each issue:
- **Severity**: ERROR (must fix) / WARNING (should fix) / INFO (suggestion)
- **Location**: File and line/section
- **Issue**: What is wrong
- **Fix**: Specific change to make

**Best practice suggestions** (non-blocking improvements) — including, where the code could fail silently (swallowed errors, unchecked empty/`null` results, HTTP 200 with an unexpected body, or an "accepted" request with no visible effect), a suggestion to log the request and response payloads per `references/best-practices.md` `## Error handling`.

**Summary**: Overall assessment in 1-2 sentences
