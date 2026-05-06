---
name: zuora-is-migration-build
description: Generate Credit Memos / Debit Memos migration implementation artifacts based on the plan
argument-hint: [migration plan reference or specific artifacts needed]
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash, Agent, mcp__zuora-mcp__zuora_codegen, mcp__zuora-mcp__ask_zuora, mcp__zuora-mcp__query_objects, mcp__zuora-mcp__get_account_summary, mcp__zuora-mcp__manage_billing_documents]
---

You are generating implementation artifacts for a Credit Memos / Debit Memos migration. The user should have a migration plan (from `/zuora-is-migration-design` or their own).

## REQUIRED INPUT: Codebase Path

**BEFORE PROCEEDING WITH ANY STEPS, YOU MUST OBTAIN THE CODEBASE PATH FROM THE USER.**

Resolve the codebase path in this order:
1. If `$ARGUMENTS` contains `codebase=<path>`, use that path directly.
2. If a `plan.md` exists in the current working directory (written by `/zuora-is-migration-design`), extract the codebase path from it — **skip asking the user**.
3. Otherwise, IMMEDIATELY ask:

"To implement the migration, I need the path to your billing/integration codebase so I can locate and update the legacy adjustment API calls. What is the full path? (e.g., `/Users/yourname/workspace/acme-billing-client`)"

Do NOT attempt to modify any code until you have this path. This is a blocker step.

## Input

The user's request: $ARGUMENTS

Expected format: `codebase=/path/to/billing-client [additional requirements]`

## Workflow

### Step 2: Review the migration plan

Understand which code modifications are needed. Ask the user:
- "Do you have a migration plan from `/zuora-is-migration-design`? If so, share the key findings about which legacy APIs need to be updated."
- If no plan exists, recommend running `/zuora-is-migration-design codebase=/path` first to inventory the code

### Step 3: Identify and update legacy adjustment code

**Key principle:** Modify existing methods to use Credit Memo APIs — do NOT create new methods.

**Process:**
1. Use `Grep` to find all SOAP calls to: `InvoiceAdjustment` / `InvoiceItemAdjustment` / `CreditBalanceAdjustment` in the codebase
2. For each call site, locate the method that contains it
3. Replace SOAP calls with REST CreditMemo API calls (using Zuora SDK)
4. Update method body only; preserve method name and interface
5. Example: Change `createInvoiceAdjustment()` body from SOAP to REST, but keep the same method signature

**What NOT to do:**
- Do NOT create `createCreditMemo()` as a new method alongside existing `createInvoiceAdjustment()`
- Do NOT add new service classes like `CreditMemoRestService`
- Modify existing code paths in-place, don't introduce parallel implementations
- Do NOT rename or change existing method names — modify the implementation in-place, preserve the original signature
- When unsure how to migrate a call, do NOT guess — list the uncertain items and ask the user before proceeding

**Validation and reconciliation:**
- Create validation scripts to verify Credit Memo behavior matches legacy semantics
- Verify that bill run automatically generates CreditMemo for negative charges
- Include pre/post migration comparison logic

### Step 3: Implementation approach

**Modify existing methods, do NOT introduce new ones:**
- Update existing method bodies to use REST CreditMemo APIs instead of legacy SOAP
- Keep the same method names, packages, and interfaces to avoid breaking changes
- Example: `InvoiceAdjustmentService.createAdjustment()` changes from SOAP to REST internally, but external callers see no difference

**Determine the correct API class before writing any code:**
- Call `zuora_codegen list_api_classes` to find the relevant API class
- Call `zuora_codegen get_class_apis` to list available methods in that class
- Do NOT hardcode API class names
- Follow the mandatory workflow: `code_guidance` → `get_api_details` → `get_model_details` → `code_rules`

**Use Zuora SDK for REST calls:**
- Use `com.zuora.model.*` classes for request/response objects
- Use `com.zuora.api.CreditmemosApi` (or similar) from SDK
- Initialize with basic auth using credentials from config
- Do NOT implement manual HTTP calls or custom JSON parsing

**Handle SOAP→REST transition:**
- Replace SOAP service calls with REST equivalents in existing method implementations
- Test that existing callers continue to work without code changes
- Update integration tests to verify REST behavior

**Code organization:**
- Keep modified code in existing package structure
- Test classes: Update existing test classes to verify behavior (do NOT create separate `*RestTest` classes)
- **Important:** When renaming test classes, ensure file names match Java naming conventions (file name = public class name with `.java` extension)

**When multiple IS APIs could apply — ask before coding**

Some legacy operations (e.g., `CreditBalanceAdjustment`, `InvoiceItemAdjustment`) can be migrated to more than one IS API, each with a different business meaning. Do NOT pick silently. When you are unsure which IS API matches the business intent of the original code, ask the user.

For example, a method that reduces an invoice balance could map to:
- `PUT /v1/creditmemos/{id}/apply` — if an existing Credit Memo is being applied
- `PUT /v1/invoices/{invoiceKey}/write-off` — if a new write-off Credit Memo should be created and applied atomically

These have different accounting implications. Present the options and their business meanings to the user and wait for confirmation before writing any code.

Apply this principle any time you identify ambiguity, not just for write-off scenarios.

### Step 5: Generate supporting artifacts

Write to files:
- Migration scripts (in user's preferred language)
- Validation scripts with expected vs actual comparisons
- Runbook with step-by-step execution instructions
- Code review checklist for API changes

### Step 7: Read reference materials

Read these references to ensure generated code follows established patterns:
- `${CLAUDE_PLUGIN_ROOT}/references/is-migration-patterns.md` — phases, object mappings, API operations for Credit Memos / Debit Memos
- `${CLAUDE_PLUGIN_ROOT}/references/is-migration-api-reference.md` — field-level mappings for legacy adjustments → Credit Memo objects
- `${CLAUDE_PLUGIN_ROOT}/references/best-practices.md` — API integration standards

### Step 8: Suggest validation

- Run all scripts in sandbox first
- Use `mcp__zuora-mcp__get_account_summary` to verify account state after Credit Memo conversion
- Use `mcp__zuora-mcp__manage_billing_documents` to verify Credit Memo and Debit Memo generation
- Run `/zuora-validate` on generated code
- Verify REST services work correctly and legacy SOAP adjustment services are properly replaced/removed
