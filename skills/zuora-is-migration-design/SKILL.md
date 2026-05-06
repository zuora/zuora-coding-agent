---
name: zuora-is-migration-design
description: Produce Credit Memos / Debit Memos migration strategy, code inventory, and phases
argument-hint: [codebase path and migration context]
allowed-tools: [Read, Write, Glob, Grep, Bash, Agent, AskUserQuestion, Skill, mcp__zuora-mcp__ask_zuora, mcp__zuora-mcp__query_objects, mcp__zuora-mcp__zuora_codegen, mcp__zuora-mcp__get_account_summary]
---

You are producing a Credit Memos / Debit Memos migration plan. This plan guides the migration from legacy invoice adjustments (InvoiceAdjustment, InvoiceItemAdjustment, CreditBalanceAdjustment) to the modern Credit Memo and Debit Memo APIs.

## REQUIRED INPUT: Codebase Path

Resolve the codebase path before any analysis:

1. If `$ARGUMENTS` contains `codebase=<path>`, use that path directly and inform the user:
   > "Analyzing codebase at: `<resolved-path>`"

2. If no path is provided, run `pwd` to get the current working directory, then ask:
   > "No codebase path was provided. I will use the current working directory:
   > `<pwd-result>`
   >
   > Is this correct, or would you like to specify a different path? (press Enter to confirm, or type the path)"

   **STOP. Wait for the user to confirm or provide a path before continuing.**

Do NOT proceed with any analysis until the path is confirmed.

## Input

The user's migration context and codebase path: $ARGUMENTS

Expected format: `codebase=/path/to/billing-client` or `codebase=/path/to/billing-client context:tenant is production with 500 accounts`

## Workflow

> **When unsure about any aspect of the migration analysis, do NOT guess — list the uncertain items and ask the user before proceeding.**


### Step 1: Assess current state

Gather context about the tenant's current state:
- Ask the user about their tenant: sandbox or production? How many accounts/subscriptions?
- Call `mcp__zuora-mcp__ask_zuora` to understand IS capabilities and prerequisites
- If the tenant is connected, use `mcp__zuora-mcp__query_objects` to inspect:
  - Account count and billing models in use
  - Invoice volume and credit balance usage
  - Payment application patterns
  - Custom integrations that reference invoices

Use `mcp__zuora-mcp__get_account_summary` on a few representative accounts to understand the current billing structure.

### Step 2: Code inventory — identify legacy adjustment usage

Search the codebase (at the path provided) for usage of legacy adjustment APIs:
- Use `Grep` to find references to: `InvoiceAdjustment`, `InvoiceItemAdjustment`, `CreditBalanceAdjustment`
- Look for SOAP API calls, method names, or class references
- Document:
  - Which files/classes use each legacy adjustment type
  - How many call sites exist
  - Whether usage is in core business logic or isolated helper functions
- Example findings to report: "Found 12 references to InvoiceAdjustment in service layer; 3 references in integration tests"

#### Resolving intent vs. implementation conflicts

When reading legacy code, **method names and existing comments are the source of truth for intent**. The implementation may have used a different or incorrect API due to legacy limitations.

For each legacy adjustment call site found:
1. Read the method name, class name, and any existing comments/Javadoc first.
2. Read the implementation second.
3. If they conflict (e.g., method is named `writeOffInvoice` but the body uses `CreditBalanceAdjustment type=Decrease`, which is a credit-apply operation, not a write-off):
   - **Do NOT guess which IS API to use.**
   - **Do NOT infer intent from the implementation.**
   - List the conflict explicitly and ask the user, for example:
     > "Method `writeOffInvoice` uses `CreditBalanceAdjustment type=Decrease` in its implementation,
     > but a write-off and a credit-apply are different IS operations:
     > - Write-off: `PUT /v1/invoices/{invoiceKey}/write-off`
     > - Apply existing credit memo: `PUT /v1/credit-memos/{creditMemoKey}/apply`
     >
     > Which is the correct IS mapping for this method?"
4. **Do NOT rename or change method names or class names** during migration — they express business intent.

### Step 3: Identify integration impacts

Ask the user about:
- Downstream systems that consume billing documents (ERP, tax engines, reporting)
- Custom reports or exports that reference adjustments
- Payment gateway integrations
- Dunning and collections processes
- Revenue recognition workflows

### Step 4: Read reference materials

First, list all files under `${CLAUDE_PLUGIN_ROOT}/references/` to understand what is available. Then read every file that is relevant to Credit Memos, Debit Memos, Invoice Settlement, or the APIs being migrated. Do not hardcode file names — the contents of the references folder may change across versions.

### Step 5: Check API requirements

Call `mcp__zuora-mcp__zuora_codegen` with `get_api_details` to understand REST API requirements for credit memos and debit memos.

### Step 7: Produce the migration plan

Deliver a structured document with the codebase path prominently noted:

**Executive summary**: What Credit Memos / Debit Memos migration is, why it matters, scope, and timeline

**Codebase inventory**: 
- Path analyzed: [record the path]
- Legacy adjustment API usage found:
  - InvoiceAdjustment: [file references and counts]
  - InvoiceItemAdjustment: [file references and counts]
  - CreditBalanceAdjustment: [file references and counts]
- Estimated effort: Based on code spread

**Current state assessment**: Summary of tenant usage patterns, custom integrations, and downstream impacts

**Migration phases**:
1. **Assessment** — code inventory (done above), downstream impact analysis
2. **Code refactoring** — update each legacy adjustment call to use REST Credit Memo API
   - When adding or updating comments on refactored methods, always include:
     - **Before:** what the legacy code did (e.g., `// Before: CreditBalanceAdjustment type=Decrease via SOAP`)
     - **After:** what the IS code does (e.g., `// After: PUT /v1/invoices/{invoiceKey}/write-off`)
   - Do NOT remove or overwrite existing comments — append the Before/After note below them.
   - Do NOT rename method names or class names.
3. **Integration updates** — update downstream systems to consume Credit Memo / Debit Memo objects
4. **Validation** — verify behavior matches legacy semantics
5. **Production rollout** — deploy updated code

**Risk matrix**: For each risk — likelihood, impact, mitigation

**Validation checklist**: Code review points, integration test scenarios, edge cases

**Dependencies and prerequisites**: API version, Zuora SDK version, team skill with REST APIs

---

## CONFIRMATION GATE

After completing the plan:

1. Present the full plan to the user
2. Write the plan to **`plan.md`** in the codebase root (or current working directory)
3. Use the `AskUserQuestion` tool to ask:

   - question: "Plan saved to `plan.md`. Do you want to proceed with implementation?"
   - options: "Yes, run /zuora-is-migration-build" and "No, I'll review the plan first"

**STOP. Do NOT continue until the user answers.**

4. If the user selects "Yes, run /zuora-is-migration-build", immediately invoke the `Skill` tool with `skill: "zuora-coding-agent:zuora-is-migration-build"`.
5. If the user selects "No", stop and let the user know the plan is saved and they can run `/zuora-is-migration-build` manually when ready.
