---
name: zuora-is-migration-build
description: Generate Credit Memos / Debit Memos migration implementation artifacts based on the plan
argument-hint: [migration plan reference or specific artifacts needed]
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash, Agent, mcp__zuora-mcp__zuora_codegen, mcp__zuora-mcp__ask_zuora, mcp__zuora-mcp__query_objects, mcp__zuora-mcp__get_account_summary, mcp__zuora-mcp__manage_billing_documents]
---

Codex-only path resolution: When an instruction refers to `${CLAUDE_PLUGIN_ROOT}`, treat it as the root of this installed plugin. In Codex, resolve that root as the ancestor directory containing `skills/`, `references/`, and `.codex-plugin/`.


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

## Tool routing

Use local code search and file edits for migration implementation work. Use `mcp__zuora-mcp__zuora_codegen` for REST API classes, endpoint details, model fields, enum values, and SDK rules. Use account summary and billing document tools for verification. `mcp__zuora-mcp__ask_zuora` is allowed only as a fallback for a specific IS capability or accounting-semantics question that remains after references and codegen are checked. If business intent is unclear, ask the user to choose the intended mapping before changing code.

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

### Step 6: Data Warehouse SQL Rewrite

**Run this step only when the migration plan (or the user) indicates DW requirements exist.**

Read `${CLAUDE_PLUGIN_ROOT}/references/is-migration-dw-patterns.md` before generating any SQL.

#### 6a — Collect customer SQL

If the user has not already provided their DW SQL/models, ask:

"Please share the SQL queries or model files that reference legacy Zuora settlement objects (`InvoicePayment`, `RefundInvoicePayment`, `CreditBalanceAdjustment`, `InvoiceAdjustment`, `InvoiceItemAdjustment`). You can paste the SQL directly, provide file paths, or point to your dbt project directory."

Also ask or confirm:
- "What DW tooling do you use? (e.g., dbt, Fivetran, raw SQL, Snowflake views, Looker PDT)"
- "Confirmed sync mode: incremental or full historical?" (should already be in the plan; re-confirm if unclear)

**STOP. Wait for the answers before producing SQL.**

#### 6b — Analyze the customer SQL

For each SQL file or query provided:
1. Identify every legacy settlement object referenced: `InvoicePayment`, `RefundInvoicePayment`, `CreditBalanceAdjustment`, `InvoiceAdjustment`, `InvoiceItemAdjustment`
2. Note table/view naming style (dbt `{{ ref() }}`, schema.table, view names, etc.)
3. Note field names used — they may differ from dbt staging model convention
4. Determine which IS object(s) replace each legacy reference (use the mapping table in `is-migration-dw-patterns.md`)

#### 6c — Generate IS-compatible rewrites

Apply the correct pattern from `is-migration-dw-patterns.md` based on sync mode:

**Incremental sync:**
- Replace `InvoicePayment` CTEs with `PaymentApplication` (Pattern 1)
- Replace `RefundInvoicePayment` CTEs with `RefundApplication` (Pattern 2)
- Retain `CreditBalanceAdjustment`, `InvoiceAdjustment`, `InvoiceItemAdjustment` unchanged (historical pre-IS records)
- Add net-new queries for `CreditMemo`/`CreditMemoItem` (Pattern 4) and `DebitMemo`/`DebitMemoItem` (Pattern 5)
- Adapt table name style to match the customer's tooling (replace `stg_zuora__*` refs with their actual table names if not using dbt)

**Full historical sync:**
- Apply the UNION ALL + anti-join deduplication pattern for payments (Pattern 6) and refunds (Pattern 7)
- Retain `CreditBalanceAdjustment` as-is — no IS equivalent (Pattern 8)
- Add net-new queries for `CreditMemo` and `DebitMemo` (Patterns 4 and 5)

**Mixed sync mode:**
- Ask which models are incremental and which are full sync, then apply the appropriate pattern per model

**Adapt to the customer's DW tooling:**
- dbt: use `{{ ref('stg_zuora__<object>') }}` syntax, preserve model structure and CTE style
- Fivetran / raw SQL: use `<schema>.<table>` notation matching their warehouse; omit dbt macros
- If the customer uses a custom staging layer, substitute their actual table/view names wherever the patterns use `stg_zuora__*`
- Preserve the customer's existing field aliases, column order, and SQL style — minimize diff size

#### 6d — Handle net-new documents (CreditMemo / DebitMemo)

CreditMemo and DebitMemo have no pre-IS equivalent — these are entirely additive. For each:
1. Produce a new model/query based on Pattern 4 (CreditMemo) or Pattern 5 (DebitMemo)
2. Adapt field names to match the customer's schema
3. Confirm sign convention with the customer: CreditMemo items default to negative `transaction_amount`; DebitMemo items default to positive

#### 6e — Output

Write each rewritten query to a file named `<original_filename>_is_rewrite.sql` (or update in-place if the user prefers). Include inline comments marking every IS change (use the `-- IS:` comment prefix convention from `is-migration-dw-patterns.md`).

At the end of this step, produce a summary table:

| Original model | Legacy objects replaced | IS objects used | Sync pattern applied | New file |
|---|---|---|---|---|
| [model name] | InvoicePayment | PaymentApplication | Incremental | [filename] |
| ... | | | | |

Also list any net-new models created for CreditMemo / DebitMemo.

#### 6f — DW validation checklist

Output a checklist the customer can use before deploying:
- [ ] Confirm DW pipeline syncs `payment_application`, `credit_memo`, `debit_memo`, `refund_application` tables
- [ ] Validate staging model field names match customer's DW schema
- [ ] Run IS-rewritten models against sandbox data
- [ ] Compare output row counts and amounts against legacy models for overlapping historical period
- [ ] Confirm no records are double-counted (run anti-join check: `COUNT(*)` on the union result vs each side separately)
- [ ] Validate sign conventions on CreditMemo / DebitMemo amounts with AR/finance team
- [ ] Enable new `CreditMemo` / `DebitMemo` objects in DW sync tool if not already present

### Step 7: Read reference materials

Read these references to ensure generated code follows established patterns:
- `${CLAUDE_PLUGIN_ROOT}/references/is-migration-patterns.md` — phases, object mappings, API operations for Credit Memos / Debit Memos
- `${CLAUDE_PLUGIN_ROOT}/references/is-migration-api-reference.md` — field-level mappings for legacy adjustments → Credit Memo objects
- `${CLAUDE_PLUGIN_ROOT}/references/best-practices.md` — API integration standards
- `${CLAUDE_PLUGIN_ROOT}/references/is-migration-dw-patterns.md` — DW object mapping, sync mode patterns, SQL examples, and pitfalls (read when DW requirements exist)

### Step 8: Suggest validation

- Run all scripts in sandbox first
- Use `mcp__zuora-mcp__get_account_summary` to verify account state after Credit Memo conversion
- Use `mcp__zuora-mcp__manage_billing_documents` to verify Credit Memo and Debit Memo generation
- Run `/zuora-validate` on generated code
- Verify REST services work correctly and legacy SOAP adjustment services are properly replaced/removed
