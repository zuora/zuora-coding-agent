# UI Test Doc Format Specification

**Path convention:** Paths below are relative to the **UAT workspace root** (default `<git-root>/uat/`).

## Overview

UI test docs are descriptive markdown files that tell the AI how to execute UI steps via Playwright MCP. They live alongside API test scripts and are consumed by the **zuora-uat-execute-ui** worker (`/zuora-uat-build` and `/zuora-uat-run`).

## File Location

```
execution/tests/test_scenarios/test_<feature>/ui_steps_tr<n>.md
```

Each UI test doc corresponds to a single TR's UI steps.

## Frontmatter

Every UI test doc begins with YAML frontmatter:

```yaml
---
feature: <feature_slug>
tr_index: TR<n>
depends_on_api_test: test_<feature>_tr<n>_api.py
environment_keys:
  - ui_base_url
  - ui_authentication.username
  - ui_authentication.password
---
```

| Field | Required | Description |
|-------|----------|-------------|
| `feature` | Yes | Feature slug matching the test directory name (e.g., `billingops_billing_document_management`) |
| `tr_index` | Yes | TR identifier (e.g., `TR1`, `TR2`) |
| `depends_on_api_test` | Yes | Filename of the API test that must run first |
| `environment_keys` | Yes | Config keys from `execution/config/test_config.yaml` needed for UI execution |

## Document Structure

```markdown
---
feature: <feature_slug>
tr_index: TR<n>
depends_on_api_test: test_<feature>_tr<n>_api.py
environment_keys: [ui_base_url, ui_authentication.username, ui_authentication.password]
---

# UI Steps - <Feature> TR<n>: <Short Description>

## Prerequisites

- API test `<depends_on_api_test>` must have run successfully
- Required data from debug log: <list of variables>
- Debug log location: `execution/debugging/{Category}_{Subcategory}_TR{N}_*.log`

## Data Extraction

Extract these values from the most recent matching debug log:

| Variable | Source Step | JSON Path |
|----------|-----------|-----------|
| `account_id` | Step 2.5: Post Invoice | `response_data.accountId` |
| `invoice_number` | Step 2.5: Post Invoice | `response_data.invoiceNumber` |

## Steps

### Step 1: <Step Title>
- **Action**: <What to do — navigate, click, type, etc.>
- **Wait**: <What to wait for before proceeding>
- **Expected**: <What should be visible/true after this step>
- **Verification**: <Specific checks to perform>

### Step 2: <Step Title>
...
```

## Step Fields

### Action

Describes what the AI should do using Playwright MCP tools. Use template variables in `{curly_braces}` for values extracted from the debug log or config.

```markdown
- **Action**: Navigate to `{ui_base_url}/platform/apps/com_zuora/account/{account_id}`
- **Action**: Click the Zuora AI icon in the bottom-right corner
- **Action**: Type `Generate the PDF for invoice {invoice_number}` into the chat input and press Enter
```

### Wait

Specifies what condition must be met before the step is considered loaded/ready. Maps to Playwright MCP wait strategies.

```markdown
- **Wait**: Text "Zuora AI" visible in side panel header
- **Wait**: Async outcome ready — use **Bounded snapshot polling** in `UI_TEST_EXECUTION_GUIDELINE.md` (pick `W`: 30 / 10 / 5; max five rounds; hard refresh on unchanged)
- **Wait**: Page URL contains `/account/`
```

### Expected

High-level description of the expected outcome.

```markdown
- **Expected**: Side panel opens with Zuora AI assistant
- **Expected**: Agent confirms PDF generation and lists available files
```

### Verification

Specific, testable checks. These become assertions during execution.

```markdown
- **Verification**: 
  - Panel header contains "Zuora AI"
  - Chat input field is visible and enabled
  - No error banners present
```

## Shared staging tenant — Zuora AI verification phrasing

Cross-account Zuora AI on **shared staging** follows **`SHARED_STAGING_TENANT_POLICY.md`** (same directory as this file). **Verification** bullets should require **non-fabrication**, **sound internal arithmetic**, and consistency with **named entities** from the debug log when cited—not “the response must contain **only** accounts/rows created by this test” for **unscoped** natural-language prompts.

**Optional frontmatter keys** (omit unless useful):

| Key | Values | Purpose |
|-----|--------|---------|
| `verification_scope` | `tenant_wide`, `named_cohort` | Hints whether zuora-uat-execute-ui should default to Tier B vs Tier A judgment (`SHARED_STAGING_TENANT_POLICY.md`). When omitted, infer from whether prompts name specific account/subscription identifiers. |

## Template Variables

Variables in `{curly_braces}` are resolved at execution time from two sources:

1. **Debug log data**: Extracted from the API test's debug log (e.g., `{account_id}`, `{invoice_number}`)
2. **Environment config**: From `test_config.yaml` (e.g., `{ui_base_url}`, `{username}`)

## Zuora AI Panel Interaction Patterns

Many UI test docs involve interacting with the Zuora AI assistant. Standard patterns:

### Opening the AI Panel — Direct Navigation (Preferred for BillingOps)

For BillingOps agent tests, navigate directly to the Zuora AI full-screen page:

```markdown
### Step N: Open Zuora AI Full-Screen Page
- **Action**: Navigate directly to `{ui_base_url.replace('/apps','')}/platform/apps/zuora-ai` (see `UI_TEST_EXECUTION_GUIDELINE.md` — Direct Zuora AI Navigation).
- **Wait**: Panel header shows "Zuora AI" and chat input field is visible
- **Expected**: Full-screen AI assistant panel is open and ready for input
- **Verification**: Panel header contains "Zuora AI"; chat input field is visible and enabled; no error state
```

### Opening the AI Panel — Side Panel (When Page Context Required)

When the test requires the AI to be opened from a specific page context:

```markdown
### Step N: Open Zuora AI Panel
- **Action**: Click the Zuora AI icon (floating button, bottom-right area of the page). If a side panel opens, click the expand/full-screen icon to enter full-screen mode.
- **Wait**: Panel header shows "Zuora AI" and chat input is visible
- **Expected**: Full-screen AI assistant panel is open
- **Verification**: Chat input field is present; no error state
```

### Sending a Prompt

```markdown
### Step N: Submit Prompt
- **Action**: Type the prompt with `browser_type` (slowly) and submit via Send (`browser_run_code`); do not use Enter in full-screen Zuora AI
- **Wait**: Agent response — **Bounded snapshot polling** with `W=30` (see `UI_TEST_EXECUTION_GUIDELINE.md`)
- **Expected**: Agent processes the request and returns a response
- **Verification**: <specific to the prompt>
```

### Agent Confirmation Handling

```markdown
**Note**: If the agent asks "Shall I proceed?" or similar confirmation, reply "Yes, please proceed" and continue waiting for the final result.
```

## Multi-Turn Conversations

For TRs that test multi-turn agent conversations, number steps sequentially and note context dependencies:

```markdown
### Step 3: Follow-up Prompt (depends on Step 2 response)
- **Action**: Type `Download the PDF` — this references the file listing from Step 2
- **Wait**: Agent response with download confirmation
- **Expected**: Agent uses the file ID from the Step 2 listing without re-asking
- **Verification**: Download confirmation references the correct file
```

## Error Scenario Steps

For steps that intentionally test error handling:

```markdown
### Step N: Invalid Input Error Handling
- **Action**: Type `Email credit memo CM-INVALID-99999 to test@example.com`
- **Wait**: Agent response appears
- **Expected**: Agent returns a clear error or not-found message
- **Verification**:
  - Response indicates the document was not found or does not exist
  - Agent does NOT fabricate a success response
  - Error message is user-friendly
```

## Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| File name | `ui_steps_tr<n>.md` | `ui_steps_tr1.md` |
| Feature slug | snake_case matching directory | `billingops_billing_document_management` |
| Step numbering | Sequential integers | Step 1, Step 2, Step 3 |
| Template variables | snake_case in curly braces | `{account_id}`, `{invoice_number}` |
| Debug log files (`execution/debugging/`) | Same as testmatrix `feature` id | `BillingOps_Billing_Document_Management_TR1_*.log` |
| Report paths | Same testmatrix `feature` id | `BillingOps_Billing_Document_Management` |
