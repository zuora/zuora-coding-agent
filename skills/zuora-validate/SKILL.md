---
name: zuora-validate
description: Validate generated code, payloads, or approach against Zuora patterns
argument-hint: [file path or inline code/payload]
allowed-tools: [Read, Glob, Grep, Bash, Agent, mcp__zuora-mcp__zuora_codegen, mcp__zuora-mcp__ask_zuora, mcp__zuora-mcp__query_objects]
---

You are validating Zuora-related code, API payloads, or design approaches against known Zuora patterns and best practices.

## Input

What to validate: $ARGUMENTS

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

Call `mcp__zuora-mcp__ask_zuora` for any domain-level questions about whether the approach is correct for the Zuora product area being used (Billing, Revenue, CPQ, Payments).

### Step 5: Report findings

Deliver a structured validation report:

**Status**: PASS / WARN / FAIL

**Issues found** (if any):
For each issue:
- **Severity**: ERROR (must fix) / WARNING (should fix) / INFO (suggestion)
- **Location**: File and line/section
- **Issue**: What is wrong
- **Fix**: Specific change to make

**Best practice suggestions** (non-blocking improvements)

**Summary**: Overall assessment in 1-2 sentences
