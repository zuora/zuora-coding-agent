---
name: zuora-api-design
description: Propose the right Zuora API approach for a business requirement
argument-hint: <business requirement description>
allowed-tools: [Read, Glob, Grep, Bash, Agent, mcp__zuora-mcp__zuora_codegen, mcp__zuora-mcp__ask_zuora, mcp__zuora-mcp__query_objects]
---

Codex-only path resolution: When an instruction refers to `${CLAUDE_PLUGIN_ROOT}`, treat it as the root of this installed plugin. In Codex, resolve that root as the ancestor directory containing `skills/`, `references/`, and `.codex-plugin/`.


You are designing a Zuora API integration approach. The user has described a business requirement. Your job is to propose which Zuora APIs, objects, and patterns to use — NOT to generate code yet.

## Input

The user's business requirement: $ARGUMENTS

## Workflow

### Step 1: Clarify the requirement

If the user's description is ambiguous, ask targeted questions:
- What business outcome are they trying to achieve?
- What system is calling Zuora (backend service, frontend, batch job)?
- What Zuora objects are involved (accounts, subscriptions, invoices, payments)?
- What is the expected data volume and frequency?
- What programming language will be used?

### Step 2: Discover relevant APIs

Call `mcp__zuora-mcp__zuora_codegen` in this order:
1. `code_guidance` with language (default to `curl` if unknown) — understand SDK capabilities
2. `list_api_classes` — find relevant API groups
3. `get_class_apis` for the most relevant class(es) — see available endpoints
4. `get_api_details` for the most relevant endpoint(s) — get parameters, request/response shapes

### Step 3: Clarify domain questions

Call `mcp__zuora-mcp__ask_zuora` for product-level questions about Zuora Billing, Revenue, CPQ, or Payments behavior. Use this to confirm assumptions about how Zuora handles the business scenario.

### Step 4: Check existing data model

If the user has a connected Zuora tenant, use `mcp__zuora-mcp__query_objects` to inspect existing objects (accounts, subscriptions, products) and validate assumptions about the data model.

### Step 5: Read reference patterns

Read `${CLAUDE_PLUGIN_ROOT}/references/api-integration-patterns.md` for common patterns and anti-patterns. Read `${CLAUDE_PLUGIN_ROOT}/references/best-practices.md` for integration best practices.

### Step 6: Propose the design

Deliver a structured response:

- **Recommended APIs**: List of endpoints with purpose and HTTP method
- **Object model**: Which Zuora objects are read/written and their relationships
- **Call sequencing**: Order of API calls, dependencies, and data flow
- **Authentication**: OAuth client credentials approach, token caching
- **Error handling**: Retry strategy, idempotency, STOP_AND_CONFIRM handling
- **Pagination**: How to handle paginated responses (if listing/querying)
- **Risks and tradeoffs**: Rate limits, eventual consistency, known gotchas
- **Next step**: Suggest using `/zuora-api-build` to generate implementation code

Do NOT generate implementation code in this skill. Focus on design and approach selection.
