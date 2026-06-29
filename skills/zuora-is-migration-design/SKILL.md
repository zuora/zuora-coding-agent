---
name: zuora-is-migration-design
description: Produce Credit Memos / Debit Memos migration strategy, code inventory, and phases
argument-hint: [codebase path and migration context]
allowed-tools: [Read, Write, Glob, Grep, Bash, Agent, AskUserQuestion, Skill, mcp__zuora-mcp__ask_zuora, mcp__zuora-mcp__query_objects, mcp__zuora-mcp__zuora_codegen, mcp__zuora-mcp__get_account_summary]
---

Codex-only path resolution: When an instruction refers to `${CLAUDE_PLUGIN_ROOT}`, treat it as the root of this installed plugin. In Codex, resolve that root as the ancestor directory containing `skills/`, `references/`, and `.codex-plugin/`.


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

## Tool routing

Use local code search and bundled IS references for code inventory, legacy API detection, mapping tables, and migration-plan structure. Use `mcp__zuora-mcp__zuora_codegen` for API details and model requirements, `mcp__zuora-mcp__query_objects` / `mcp__zuora-mcp__get_account_summary` for tenant state, and `mcp__zuora-mcp__ask_zuora` only when a specific IS capability, prerequisite, or accounting-semantics question remains unresolved after those sources.

## Workflow

> **When unsure about any aspect of the migration analysis, do NOT guess — list the uncertain items and ask the user before proceeding.**


### Step 1: Assess current state

Gather context about the tenant's current state:
- Ask the user about their tenant: sandbox or production? How many accounts/subscriptions?
- Call `mcp__zuora-mcp__ask_zuora` for unresolved IS capability or prerequisite questions; prefer checking the bundled IS references and codegen first when they are likely to have the answer.
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

### Step 3b: Data Warehouse Assessment

Use `AskUserQuestion` to ask the following two questions **in a single call**:

**Question 1:** "Does your system include a Data Warehouse or BI reporting layer that reads Zuora data? (e.g., dbt models, Fivetran/HVR pipelines, Looker, raw SQL reports, Snowflake/BigQuery views)"
- Options: "Yes — we have DW/BI queries that read Zuora tables" / "No — no DW layer to update"

**STOP. Wait for the answer before continuing.**

If the user answers **No**, skip the rest of Step 3b and proceed to Step 4.

If the user answers **Yes**, ask:

**Question 2:** "How does your DW pipeline sync Zuora data — incremental (only new/changed records each run) or full historical sync (full rebuild from scratch each run)?"
- Options: "Incremental sync — we only process new/changed records" / "Full historical sync — we rebuild history on every run" / "Mixed — some models incremental, some full sync"

Record the DW sync mode. Then ask the user to share their existing SQL queries or model files that read from the following legacy Zuora objects (one or more may apply):
- `InvoicePayment` / `invoice_payment`
- `RefundInvoicePayment` / `refund_invoice_payment`
- `CreditBalanceAdjustment` / `credit_balance_adjustment`
- `InvoiceAdjustment` / `invoice_adjustment` or `InvoiceItemAdjustment`

Tell the user: "You can paste the SQL directly, provide file paths, or describe which tables your models use. I will produce IS-compatible rewrites in the build phase."

Document everything collected here in the plan's DW section (see Step 7).

### Step 4: Read reference materials

First, list all files under `${CLAUDE_PLUGIN_ROOT}/references/` to understand what is available. Then read every file that is relevant to Credit Memos, Debit Memos, Invoice Settlement, or the APIs being migrated — **including `is-migration-dw-patterns.md` when DW requirements were identified in Step 3b**. Do not hardcode file names — the contents of the references folder may change across versions.

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

**Data Warehouse section** *(include only when DW requirements were identified in Step 3b)*:
- Sync mode: [incremental / full historical / mixed]
- DW tooling: [dbt / Fivetran / raw SQL / other]
- Affected models / queries:
  - [model name]: reads [InvoicePayment / RefundInvoicePayment / CreditBalanceAdjustment / etc.] → IS equivalent: [PaymentApplication / RefundApplication / retain as-is / etc.]
- Net-new models required (no legacy equivalent):
  - `dim_transactions_creditmemo` — reads `CreditMemo` + `CreditMemoItem`
  - `dim_transactions_debitmemo` — reads `DebitMemo` + `DebitMemoItem`
- Pipeline readiness: confirm DW sync includes `payment_application`, `credit_memo`, `debit_memo`, `refund_application` tables
- IS-compatible SQL rewrites will be generated in the build phase (reference: `is-migration-dw-patterns.md`)

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
