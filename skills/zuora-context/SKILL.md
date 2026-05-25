---
name: zuora-context
description: This skill should be used when the user mentions "Zuora API", "Zuora SDK", "Zuora Billing", "Zuora Revenue", "Zuora CPQ", "Zuora Payments", "subscription billing", "invoice settlement", "zuora-mcp", "rate plan", "product rate plan charge", "order API", or discusses integration with Zuora systems. Do not activate for generic billing or subscription discussions that are not Zuora-specific.
version: 1.0.0
---

Codex-only path resolution: When an instruction refers to `${CLAUDE_PLUGIN_ROOT}`, treat it as the root of this installed plugin. In Codex, resolve that root as the ancestor directory containing `skills/`, `references/`, and `.codex-plugin/`.


# Zuora Context

When the user is discussing Zuora-related topics in general conversation (without invoking a specific `/zuora-` command), you have access to the zuora-mcp server which provides authoritative Zuora capabilities.

## Available MCP tools

MCP tools serve three purposes:
1. **Look up specs** — inform code generation with API metadata, field names, enum values.
2. **Perform operations on the tenant** — when the user asks to directly do something (e.g., "create a product," "query my subscriptions"), use the appropriate tool.
3. **Test/validate artifacts** — verify generated workflows, subscriptions, etc.

When generating code for the customer's repository, output Zuora REST API or SDK calls — never embed MCP tool references. If intent is ambiguous (do it now vs. write code for it), ask the user.

**Metadata & guidance tools** (for looking up API specs, field names, best practices):
- **`mcp__zuora-mcp__zuora_codegen`** — Look up API classes, endpoints, request/response models, field names, enum values, and SDK code rules. Follow the mandatory workflow: `code_guidance` → `list_api_classes` → `get_class_apis` → `get_api_details` → `get_model_details` → `code_rules`.
- **`mcp__zuora-mcp__ask_zuora`** — Ask product-level questions about Zuora Billing, Revenue, CPQ, Payments, and Central Platform. Use only for unresolved "how does Zuora handle X?" questions after local references and specialist tools do not answer the issue.
- **`mcp__zuora-mcp__sdk_upgrade`** — Help with SDK version upgrades and changelogs.

**Tenant inspection tools** (for reading live tenant data to inform code generation):
- **`mcp__zuora-mcp__query_objects`** — Query 40+ Zuora object types with filtering, sorting, and pagination. Use to inspect tenant data (accounts, subscriptions, products, etc.).
- **`mcp__zuora-mcp__get_account_summary`** — Get comprehensive account view including recent memos.

**Operational tools** (for testing/validating generated artifacts against the tenant, or other available MCP tools):
- **`mcp__zuora-mcp__manage_workflows`** / **`run_workflows`** — Import, export, list, and execute workflows in the tenant.
- **`mcp__zuora-mcp__create_subscriptions`** / **`manage_subscriptions`** — Create or manage subscriptions for validation.
- **`mcp__zuora-mcp__manage_billing_documents`** — Verify billing document generation.
- Other `manage_*` tools as needed for their specific domains.

## Tool routing

Use built-in tools for repo facts and bundled references. Use specialist MCP tools for their structured domains (`zuora_codegen` for API/spec/model details, `query_objects` for tenant data, Workflow and meter tools for their artifacts). Call `ask_zuora` only when a qualitative product-behavior or best-practice question remains, and include the exact uncertainty plus the sources already checked.

## When to invoke a dedicated skill

If the user's intent clearly maps to a dedicated skill, **do not answer generically — read that skill's `SKILL.md` and follow its workflow directly**, as if the user had invoked the command themselves.

| User intent | Dedicated skill to invoke |
|---|---|
| Designing an API integration | Read `${CLAUDE_PLUGIN_ROOT}/skills/zuora-api-design/SKILL.md` |
| Generating integration code | Read `${CLAUDE_PLUGIN_ROOT}/skills/zuora-api-build/SKILL.md` |
| Automating a business process | Read `${CLAUDE_PLUGIN_ROOT}/skills/zuora-workflow-design/SKILL.md` |
| Building a workflow | Read `${CLAUDE_PLUGIN_ROOT}/skills/zuora-workflow-build/SKILL.md` |
| Planning Invoice Settlement migration | Read `${CLAUDE_PLUGIN_ROOT}/skills/zuora-is-migration-design/SKILL.md` |
| Building Invoice Settlement migration artifacts | Read `${CLAUDE_PLUGIN_ROOT}/skills/zuora-is-migration-build/SKILL.md` |
| Planning Order API and migration | Read `${CLAUDE_PLUGIN_ROOT}/skills/zuora-order-migration-design/SKILL.md` |
| Building Order API and migration artifacts | Read `${CLAUDE_PLUGIN_ROOT}/skills/zuora-order-migration-build/SKILL.md` |
| Validating code or payloads | Read `${CLAUDE_PLUGIN_ROOT}/skills/zuora-validate/SKILL.md` |
| Reviewing implementation | Read `${CLAUDE_PLUGIN_ROOT}/skills/zuora-review/SKILL.md` |

If the intent is ambiguous, briefly clarify with the user before invoking a skill. For general Zuora questions that don't map to a skill, answer using the MCP tools and reference materials below.

## Reference materials

For deeper domain knowledge, read files from `${CLAUDE_PLUGIN_ROOT}/references/`:
- `best-practices.md` — general integration best practices
- `api-integration-patterns.md` — common API patterns
- `workflow-patterns.md` — workflow automation patterns
- `is-migration-patterns.md` — IS migration patterns
- `order-migration-patterns.md` — Order API migration patterns
