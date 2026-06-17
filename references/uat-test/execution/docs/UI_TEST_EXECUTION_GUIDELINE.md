# UI Test Execution Guideline

**Path convention:** Paths below are relative to the **UAT workspace root** (default `<git-root>/uat/`).

## Overview

This guide covers how the AI executes UI test steps via Playwright MCP. The AI reads a UI test doc (`ui_steps_tr<n>.md`), extracts test data from the API debug log, authenticates to the Zuora UI, and drives the browser step-by-step.

## Execution Flow

```
1. Read UI test doc (frontmatter + steps)
2. Find and parse the API debug log for captured variables
3. Load environment config (ui_base_url, credentials)
4. Authenticate to Zuora UI
5. Execute each step using Playwright MCP tools
6. Evaluate issues with AI-driven judgment
7. Write per-TR report (use `browser_snapshot` for page state; do not use Playwright screenshot tools)
```

## Phase 1: Data Extraction from Debug Log

Before any browser interaction, extract test data from the API debug log.

### Finding the Debug Log

1. Read `feature-log-mapping.json` in the feature's test directory for the `feature` id (testmatrix string) and TR metadata
2. Search `execution/debugging/` for the most recent file matching `{feature}_TR{N}_*.log` (same `{feature}` as reports)
3. If multiple matches, use the most recent by timestamp in filename

### Parsing the Debug Log

The debug log uses a structured format (see `DEBUGGING_MECHANISM_GUIDE.md`). Extract variables from `RESPONSE DATA` sections:

```
STEP: Step 2.5: Post Invoice
...
RESPONSE DATA:
{
  "invoiceId": "8a90000000000000000000000000002",
  "invoiceNumber": "INV00000001",
  "accountId": "8a90000000000000000000000000001",
  "accountNumber": "A00000001"
}
```

Also check `INFO:` lines at the end of the log for a summary of all captured variables.

### Variable Resolution

The UI test doc's `Data Extraction` table specifies which variables to extract and from which step. Build a variable map:

```json
{
  "account_id": "8a90000000000000000000000000001",
  "account_number": "A00000001",
  "invoice_id": "8a90000000000000000000000000002",
  "invoice_number": "INV00000001"
}
```

Replace all `{variable_name}` placeholders in the UI test doc with resolved values before execution.

## Phase 2: Authentication

### Zuora UI Login Flow

The AI authenticates using credentials from `test_config.yaml`:

```yaml
ui_base_url: https://<environment>.zuora.com/apps
ui_authentication:
  username: your-ui-user@example.com
  password: ${UI_PASSWORD}
```

**Login Steps**:

1. **Navigate** to `{ui_base_url}` using `browser_navigate`
2. **Wait** for the login page to load — look for username/email input field
3. **Fill** the username field with `{username}`
4. **Fill** the password field with `{password}`
5. **Click** the login/sign-in button
6. **Wait** for post-login page — the URL should change away from the login page, and the main application UI should be visible
7. **Handle** any post-login modals (dismiss "What's New" popups, cookie consent, etc.)

### Authentication Gotchas

- Some environments use SSO — the login page may redirect first
- The login page now defaults to "Sign in with Zuora OneID". For legacy credentials, click "Use legacy login" to expand the username/password fields before filling them
- After login, there may be a brief loading spinner before the app is ready
- If login fails, take a `browser_snapshot` for the report’s **UI evidence** section, then report — do not proceed with UI steps

### Account Page Navigation

Zuora has two URL patterns for account pages. The platform URL sometimes returns "Internal System Error" for newly created accounts:

- **Platform URL** (may fail): `{ui_base_url}/platform/apps/com_zuora/account/{account_id}`
- **Classic URL** (reliable): `{ui_base_url.replace('/apps','')}/apps/CustomerAccount.do?method=view&id={account_id}`

**Recommended pattern**: Navigate to the platform URL first. If the page shows an error or the account number is not visible after 8 seconds, fall back to the classic URL. The classic URL always works and loads the full account detail page with all sections.

### Tenant-Specific Authentication

If the test uses `tenant_suffix`, the config may have different credentials:

```yaml
staging_feature_example:
  ui_authentication:
    username: your-tenant-ui-user@example.com
    password: ${UI_PASSWORD}
```

## Phase 3: Step Execution via Playwright MCP

### Playwright MCP Tool Reference

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `browser_navigate` | Go to a URL | Navigation steps, initial page load |
| `browser_snapshot` | Get page accessibility snapshot | Check page state, find elements; primary evidence for reports (do **not** use `browser_take_screenshot`) |
| `browser_click` | Click an element | Buttons, links, icons, toggles |
| `browser_fill_form` | Fill input fields | Form inputs, search boxes |
| `browser_type` | Type text character by character | Chat inputs, text areas where fill doesn't work |
| `browser_press_key` | Press keyboard keys | Enter to submit, Escape to close |
| `browser_wait_for` | Wait for condition | Page load, element appearance |
| `browser_hover` | Hover over element | Tooltips, dropdown triggers |
| `browser_select_option` | Select from dropdown | Dropdown menus |
| `browser_evaluate` | Run JavaScript | Complex checks, scroll, extract data |
| `browser_console_messages` | Get console output | Debug JS errors |
| `browser_network_requests` | Check network activity | Verify API calls fired |
| `browser_run_code` | Run arbitrary Playwright code | Complex interactions like clicking by CSS selector, workaround for stale refs |
| `browser_tabs` | List/switch browser tabs | Required after full-screen mode opens a new tab |

**Tool friction**: Use only **`browser_run_code`** for locator-based snippets (e.g. Send). **Never** call **`browser_run_code_unsafe`** — it is not allowlisted in CI and produces permission denials without progress.

### Bounded snapshot polling (canonical)

Use this for **any** step where the UI outcome arrives asynchronously: Zuora AI replies, heavy content loads, search results, and similar “wait until visible” situations.

#### Choose base interval `W` (seconds)

Pick **one** `W` for the **entire** wait episode on that step:

| Context | `W` | Examples |
|---------|-----|----------|
| Conversation / Zuora AI assistant reply / streamed agent output | **30** | After Send; multi-tool agent runs |
| General async content after navigation or a primary user action | **10** | Lists, panels, post-submit status |
| Light UI state change | **5** | Chips, small dialogs, toggle visibility |

#### Episode algorithm (at most **five** wait rounds)

One **episode** = waiting for a **single** step’s outcome (one Wait field / one logical “until verified”).

1. After the triggering action, optionally record a **fingerprint** from `browser_snapshot` (e.g. excerpt of the conversation tail, or a short stable selector + text hash).
2. For round `k = 1` through `5`:
   - `browser_wait_for` with `"time": W * 2**(k-1)` seconds (integer). **30 → 60 → 120 → 240 → 480** when `W=30`.
   - `browser_snapshot`; evaluate **Expected** / **Verification** for that step.
   - If satisfied → **stop** (success).
   - If not satisfied and `k < 5`:
     - If the snapshot shows **no meaningful change** vs the fingerprint carried from the **previous** round → **hard refresh**: `browser_navigate` to the **exact current URL** (same `.../zuora-ai/chat/<id>` in chat TRs). Do **not** open **New Chat** or navigate to bare `/platform/apps/zuora-ai` to bypass the cap.
     - Refresh fingerprint from the latest snapshot, then go to round `k+1`.
3. After **five** rounds without success:
   - **Stop** this episode. **Do not** add a sixth round, do **not** stack extra multi-minute `browser_wait_for` calls for the **same** step, and do **not** start another full retry loop for the same step outcome.
   - Record **`performance_timeout`** or **`zuora_ai_slow_response`** (chat) in **Issues Encountered** with the schedule used (`W`, five rounds, refresh count).
   - Outcome: **`FAILED`** on the step if the TR cannot continue without this result; otherwise **`PASS_WITH_WARNING`** with an explicit performance note, or **`FAILED`** on the step and **continue** to the next step — per TR intent. **Never** spend further wall time or model turns retrying the same step.

**Maximum wall time** per episode: `W + 2W + 4W + 8W + 16W = 31W` (e.g. `W=30` → **930 s ≈ 15 min 30 s**; `W=10` → **310 s**; `W=5` → **155 s**).

#### Relation to Zuora AI “same chat” rules

Bounded polling **reloads the same chat URL** only. If the episode exhausts after five rounds, **document and advance** — do **not** spawn a new chat for the same TR to re-run the step.

### Step Execution Pattern

For each step in the UI test doc:

1. **Read** the Action, Wait, Expected, and Verification fields
2. **Execute** the Action using appropriate Playwright MCP tools
3. **Wait** for the condition in the Wait field — use **Bounded snapshot polling** for async outcomes (pick `W`: 30 / 10 / 5; max five rounds; refresh on unchanged). For purely static UI checks, a short `browser_wait_for` plus one snapshot may suffice.
4. **Verify** using the checks in the Verification field
5. **Record** the step result (PASSED, FAILED, PASS_WITH_WARNING)

Use **`browser_snapshot`** to inspect and verify the page. Do **not** call `browser_take_screenshot` or save image files for UI runs.

### Element Selection Strategy

Use `browser_snapshot` to get the accessibility tree, then identify elements by:

1. **Role + Name**: Preferred. e.g., click button named "Submit"
2. **Text content**: For links and labels
3. **Ref attribute**: From the snapshot's `ref` values

Avoid hardcoded CSS selectors — the accessibility snapshot is more stable.

## Zuora AI Panel Interaction Knowledge

### Direct Zuora AI Navigation

For BillingOps agent tests (and any test that only needs the full-screen AI chat without a specific page context), navigate directly to the Zuora AI full-screen page instead of opening the side panel from another page:

**URL**: `{ui_base_url.replace('/apps','')}/platform/apps/zuora-ai`

For example, if `ui_base_url` is `https://<environment>.zuora.com/apps`, the direct URL is `https://<environment>.zuora.com/platform/apps/zuora-ai`.

This avoids the multi-step flow of navigating to an account page, clicking the AI icon, then clicking "Full Screen Mode" (which opens a new tab). The direct URL loads the full-screen AI chat in the current tab.

### Opening the Zuora AI Assistant (Side Panel)

When a test requires the AI panel to be opened from a specific billing-context page (account pages, invoice pages, etc.) — for example, when the page context matters for the AI's behavior:

1. **Locate** the Zuora AI trigger — a floating icon/button typically in the bottom-right area of the page. Use `browser_snapshot` to find it (look for elements with text "Zuora AI", "AI Assistant", or an icon button near the bottom-right).
2. **Click** the trigger to open the side panel.
3. **Enter full-screen** if the test doc specifies it — look for an expand/maximize icon or "Full Screen Mode" link within the panel header. **Important**: Full-screen mode opens in a new browser tab. After clicking, use `browser_tabs` to select the new tab (typically the last one) before interacting with the AI.
4. **Verify** the panel is ready: the header should show "Zuora AI" and a chat input field should be visible.

### Sending Messages to the AI Agent

The Zuora AI chat input is a React-controlled `<textarea>`. Standard `fill()` sets the DOM value but does not trigger React's `onChange` handler, so the send button remains inactive. Use this reliable pattern:

1. **Find** the chat input — typically a text area at the bottom of the AI panel with placeholder "Describe what you'd like AI to do".
2. **Type** the prompt using `browser_type` with `slowly: true` (which uses `pressSequentially` to fire individual key events that React recognizes). Do NOT use `browser_fill_form` — it does not trigger React state updates.
3. **Submit** by clicking the Send arrow button (`button[aria-label="Send message"]`). Use **`browser_run_code`** with: `async (page) => { await page.locator('button[aria-label="Send message"]').click(); }`. Do **not** use `browser_run_code_unsafe`. Do NOT rely on pressing Enter — it does not submit in the full-screen panel.
4. **Wait for response**: Use **Bounded snapshot polling** with **`W = 30`** (conversation / agent output).

**Why not Enter?** The full-screen Zuora AI panel's textarea treats Enter as a newline, not submit. The only reliable submit method is clicking the send arrow button.

### Waiting for Agent Responses

Agent replies are async and may stream. **Do not** use ad-hoc “snapshot every 3s until stable” loops beyond the canonical cap. Follow **Bounded snapshot polling** with **`W = 30`**, five rounds, refresh-on-unchanged between rounds, then **stop** and record performance / fail per that section.

### Agent Confirmation Handling

The Zuora AI agent sometimes asks for confirmation before executing operations (e.g., "Shall I proceed?", "Do you want me to continue?"):

1. **Detect** confirmation prompts by checking the latest agent message for question patterns
2. **Reply** with "Yes, please proceed" (or similar affirmative)
3. **Wait** again for the actual operation result using **Bounded snapshot polling** with **`W = 30`** (new episode for that reply).

### Capturing the Chat Session URL

For tests that use the Zuora AI full-screen page (`/platform/apps/zuora-ai`), the browser URL changes to include a chat session ID after the first message exchange — e.g., `https://<environment>.zuora.com/platform/apps/zuora-ai/chat/00000000-0000-4000-8000-000000000001`. This URL is valuable for developers debugging agent behavior.

**One chat per TR**: For a given `ui_steps_tr<n>.md`, the executor must **not** click **New Chat**, must **not** navigate to bare `/platform/apps/zuora-ai` to spawn a second thread, and must **not** intentionally open another `.../chat/<uuid>` for that same TR. Continue the scenario with **new user messages** in the same thread; use explicit delimiters in the prompt when a step needs an isolated check (e.g. “New scenario — answer only this: …”). **Between different TR files** in a batch, a new chat is allowed when switching reports.

**When to capture**: Seconds after sending the first message — the URL updates to include the chat session ID after the message is sent. Capture it when the first response is received. If the agent fails to respond, still capture it before failing the test. After that, if `window.location.href` ever shows a **new** distinct chat session id (rare: accidental navigation), append it to the ordered list in the report header.

**How to capture**: Use `browser_evaluate` to run `window.location.href`. Record the first URL on `**Chat Session URL**:` and, if there is more than one distinct session id for this TR, also add `**Chat Session URLs (ordered, distinct)**:` with a numbered list in first-seen order (see **Execution Report** below).

**Where to record**: Per-TR execution report header (see **Execution Report** below). Only include these fields for tests that interact with the Zuora AI chat panel.

### Extracting Agent Responses

After the agent responds:

1. Use `browser_snapshot` to capture the full conversation
2. The agent's response is the last message block in the conversation area
3. Extract key information: operation confirmations, file IDs, error messages
4. Compare with the step's Verification criteria

### Silent Agent Failure and Retry

Occasionally the Zuora AI agent produces no visible reply — the user message appears but the assistant area stays empty or stuck. Treat this as **one bounded polling episode** on the current step.

**Scope**: Same **TR** and same **`.../zuora-ai/chat/<session-id>`** only.

**Do not**: Click **New Chat**, navigate to bare `/platform/apps/zuora-ai` without the session id, or replay earlier steps from scratch for this class of issue.

**Order** (stay within the five-round cap — do not stack unlimited “recovery” passes):
1. **Only if** the message clearly never submitted (Send stayed disabled / textarea empty): fix input, submit once, then start **Bounded snapshot polling** with `W=30`.
2. Otherwise run **Bounded snapshot polling** (`W=30`) as written: doubles, hard refresh on unchanged snapshot between rounds, max **five** waits.
3. **Optional once** before round 1 if the UI shows a benign stuck spinner: a single in-thread follow-up (“Please continue with my previous request.”) **without** resetting the chat; still counts toward the same step’s bounded episode (do not reset `k`).
4. If a refresh unblocks rendering, note `transient_rendering` where appropriate.
5. If five rounds complete with no acceptable outcome → record **`zuora_ai_slow_response`** / **`performance_timeout`**, then **FAILED** (or continue per TR) — **no** extra long `browser_wait_for` blocks and **no** second full polling episode for the **same** step.

### Common Zuora AI Selectors (Reference)

These are starting points — always verify with `browser_snapshot` as the UI may change:

- **AI trigger button**: Floating action button, typically with `button "Zuora AI"` in the snapshot
- **Chat input**: `textbox "Describe what you'd like AI to do"` — a React-controlled textarea
- **Send button**: `button[aria-label="Send message"]` — the arrow icon next to the chat input. Must be clicked via **`browser_run_code`** (never `browser_run_code_unsafe`); avoid snapshot `ref` for Send (stale refs).
- **Suggested action buttons**: Appear after agent responses as clickable chips (e.g., "Download the PDF file"). Clicking these pre-fills the textarea — you still need to click Send afterward
- **Conversation messages**: Sequential message blocks in the panel body
- **Agent response**: Message blocks from the "assistant" or "Zuora AI" sender

## Wait Strategies

### Page Navigation Waits

After `browser_navigate`, wait for the page to be ready:

```
1. browser_navigate to URL
2. browser_wait_for text/element that indicates the page loaded
3. browser_snapshot to verify page state
```

### Dynamic Content Waits

For content that loads asynchronously (agent responses, search results):

```
1. Execute the triggering action (click, type, submit)
2. Bounded snapshot polling: pick W (30 / 10 / 5), at most five browser_wait_for intervals W,2W,4W,8W,16W
3. browser_snapshot after each wait; verify expected delta
4. If unchanged vs prior fingerprint before the next round → browser_navigate (same URL) hard refresh
5. After five rounds → stop; record performance_timeout / zuora_ai_slow_response; fail or continue per TR — no further polling on this step
```

### SPA Navigation Waits

Zuora is a single-page application. After in-app navigation:

```
1. Click the navigation link/button
2. Wait for URL to change (if applicable)
3. Wait for page content to update (new heading, data loaded)
4. browser_snapshot to verify the new page state
```

## Retry Patterns

### Transient Failure Retry

If a step fails due to a transient issue (element not found, click had no effect):

1. Wait 2-3 seconds
2. Take a fresh `browser_snapshot`
3. Retry the action (max 2 retries)
4. If still failing, evaluate as a potential real failure

### Page Load Retry

If navigation times out or returns an error:

1. Wait 5 seconds
2. Retry `browser_navigate`
3. If still failing after 2 retries, proceed and document state in the report

### Stale Element Retry

If an interaction fails because the page re-rendered (SPA behavior):

1. Take a fresh `browser_snapshot`
2. Re-identify the element
3. Retry the interaction

## End-of-TR UI evidence (accessibility snapshot)

After all steps for the TR finish (any outcome), summarize final page state from the **last** `browser_snapshot` (or note `—` if there was no browser session, e.g. BLOCKED before UI).

**Chat TRs**: Scroll the **conversation** element to the bottom (not only `window`; nested scrollers count), wait briefly, then take a fresh `browser_snapshot` and quote or summarize the relevant lines in the report’s **UI evidence** section.

**Viewport**: `browser_resize` toward `1920x1400` once per TR or once per batch when reusing a session.

**Cleanup**: Before the run, remove the old `execution/reports/{Feature}_TR{N}_report.md` if present (`{Feature}` matches reports and debug logs).

**Report**: Fill **`## UI evidence`** per the **Execution Report** section below. For **Issues Encountered**, the Evidence column is a short excerpt from the accessibility tree or `—` — not image paths.

## AI-Driven Issue Evaluation

When the AI encounters an issue during execution, it evaluates the situation rather than immediately failing.

### Evaluation Process

1. **Observe**: What happened? What was expected?
2. **Classify**: Is this transient, a verification mismatch, or a real failure?
3. **Act**: Retry, relax verification, or fail with evidence
4. **Record**: Document the decision in the execution report

### Example Classifications

| Pattern | Likely Classification | Suggested Action |
|---------|----------------------|------------------|
| Element not found after page load | Transient (page still loading) | Retry after short wait |
| Click had no visible effect | Transient (JS not ready) | Retry interaction |
| Expected text not visible but page loaded | Verification may be too strict | Check for semantically equivalent content |
| HTTP 5xx / navigation timeout | Transient (server issue) | Retry navigation |
| Completely unexpected page state | Possible service bug | Fail; evidence from last `browser_snapshot` in the report |
| Stale element / detached DOM | Transient (SPA re-render) | Re-read page state |
| Agent produces no response (empty area, no spinners) | Transient or performance | **Bounded snapshot polling** then `zuora_ai_slow_response` / fail — no open-ended waits |

### Decision Record Format

Each issue produces a decision record:

```json
{
  "step": "Step_2",
  "issue": "Expected 'Active' not found in page",
  "classification": "relaxed_verification",
  "action_taken": "Found 'ACTIVE' (uppercase), treating as equivalent",
  "outcome": "PASS_WITH_WARNING",
  "evidence": "Snapshot: status cell shows ACTIVE"
}
```

### Outcome Values

| Outcome | Meaning |
|---------|---------|
| `PASSED` | Step completed as expected |
| `PASS_WITH_WARNING` | Step completed but with relaxed verification or minor deviation |
| `FAILED` | Step did not complete or critical verification failed |
| `BLOCKED` | Step could not execute (API test failed, prerequisite missing) |
| `SKIPPED` | Step intentionally skipped (not applicable in this run) |

## Verification Judgment

TRs describe the *intent* of a test — what the feature should accomplish — but they are not pixel-perfect specifications. The actual UI may present information differently than the TR's exact wording, and that is often acceptable. The AI must strike a balance: **verify the feature works correctly** without failing on cosmetic or presentational differences that don't affect the feature's purpose.

### Guiding Principle

Ask: *"Did the feature do what the TR intended?"* — not *"Does the UI match the TR word-for-word?"*

Every deviation from the TR's literal expectation must be documented as `PASS_WITH_WARNING` with a clear rationale, so a human reviewer can audit the judgment. Never silently ignore a deviation.

### Shared staging tenant and cross-account Zuora AI

Scheduled runs use **one shared staging tenant**. For **unscoped** Zuora AI prompts (tenant-wide rankings, rollups, “top N”, multi-month summaries), read **`SHARED_STAGING_TENANT_POLICY.md`** (same directory). Judge the agent on:

1. **Non-fabrication** — cited accounts, amounts, IDs, and dates must be real for the tenant (or clearly labeled estimates); invented rows → **FAILED**.
2. **Correct calculations** — totals, subtotals, and percentages must reconcile with the table or narrative the agent presented; broken internal math → **FAILED**.
3. **Validity for the prompt’s scope** — when the UI doc or TR implies tenant-wide/window-wide results, **extra** accounts or **extra** month buckets vs a seed-only doc are **not** automatic failures if they are plausible for the tenant and not fabricated. Compare to an **independent oracle** in the debug log (ZOQL/REST for the same window) when numeric proof is required.

| Situation | Typical outcome |
|-----------|-----------------|
| Agent adds rows/months or larger totals because **other real tenant data** exists; no fabrication; structure OK | **PASS_WITH_WARNING** (rationale: shared tenant; seed not exclusive universe) unless an oracle proves the numbers wrong |
| Agent numbers **contradict** a stored oracle for the same scope, or **scoped** prompt (named IDs) ignored | **FAILED** |
| UI doc still demands “only seeded cohort” on an unscoped prompt | Treat as **invalid expectation** — **PASS_WITH_WARNING** with rationale referencing the policy, and file a follow-up to fix the UI doc / test plan |

### Acceptable Deviations (PASS_WITH_WARNING)

These differences are tolerable — the feature is working correctly, but the output doesn't match the TR verbatim:

| Category | Example | Why It's Acceptable |
|----------|---------|---------------------|
| **Case differences** | TR says "Active", UI shows "ACTIVE" or "active" | Same semantic meaning |
| **Wording variations** | TR says "Invoice PDF generated", agent says "I've generated the PDF for your invoice" | Same operation confirmed |
| **Missing non-critical details** | TR expects subscription summary with 8 fields, agent returns 6 fields covering the key ones | Core information present; missing details are supplementary, not essential to the feature |
| **Formatting differences** | TR expects "$200.00", UI shows "200.00 USD" or "$200" | Same value, different presentation |
| **Order of items** | TR lists files as A, B, C; agent returns C, A, B | Same content, different ordering |
| **Extra information** | Agent response includes additional helpful context not mentioned in TR | More information than expected is not a failure |
| **Date/time format** | TR expects "2026-01-01", UI shows "Jan 1, 2026" | Same date, different format |
| **Truncation or summarization** | Agent summarizes a long list instead of showing every item | Information is conveyed, just condensed |

### Hard Failures (FAILED)

These are real problems — the feature did not work as intended:

| Category | Example | Why It's a Failure |
|----------|---------|-------------------|
| **Wrong data** | TR expects account A00000001, agent shows A00009999 | Incorrect data — feature operated on the wrong record |
| **Missing operation** | TR expects agent to execute `generate_pdf`, agent did not call the tool | Core operation was not performed |
| **Fabricated success** | Agent says "Email sent successfully" but the operation errored | False positive — dangerous for production trust |
| **Security/permission error** | "You don't have permission to perform this action" | Environment or feature configuration issue |
| **Wrong operation** | TR expects email, agent executed download instead | Fundamental misunderstanding of the request |
| **Data corruption** | Agent modified data it should only have read | Destructive side effect |

### Gray Areas — Use Judgment

Some situations require contextual evaluation:

- **Partial success**: Agent completed 3 of 4 sub-operations. Is the missing one critical to the TR's intent? If the TR is testing that the agent can "manage billing documents" and it handled 3 types correctly but stumbled on one, consider `PASS_WITH_WARNING` for the successful parts and `FAILED` for the specific sub-step.

- **Equivalent but different path**: TR says "click the download button", but the agent provided a download link instead. If the user can still get the file, the feature worked — `PASS_WITH_WARNING`.

- **Missing detail in a summary**: TR expects a subscription summary to include the charge amount, but the agent's response covers subscription status, term dates, and rate plan without the exact charge amount. The feature (summarization) worked, but a specific detail is absent. This is `PASS_WITH_WARNING` — the feature's purpose was fulfilled, the missing detail is worth noting but not a functional failure.

- **Slow but within bounded polling**: If the operation completed within the **five-round** schedule for the chosen `W`, note latency in **Issues**; if still correct, `PASS_WITH_WARNING` is acceptable. If the episode **exhausted** five rounds, that is a **`performance_timeout`** / **`zuora_ai_slow_response`** outcome for that step — not an invitation to keep waiting.

### Recording Verification Judgments

Every `PASS_WITH_WARNING` must include:

```json
{
  "step": "Step_3",
  "issue": "Agent response missing charge amount detail mentioned in TR",
  "classification": "acceptable_deviation",
  "rationale": "TR expects subscription summary with charge amount. Agent returned summary with status, term, and rate plan but omitted the $200/month charge detail. The summarization feature worked correctly — the missing detail is supplementary.",
  "tr_expectation": "Summary includes charge amount",
  "actual_result": "Summary covers status, term, rate plan; charge amount absent",
  "outcome": "PASS_WITH_WARNING"
}
```

The `rationale` field is critical — it explains *why* this deviation is acceptable. A future reviewer should be able to read the rationale and agree with the judgment without needing additional context.

## Execution Report

After all steps complete, produce a per-TR execution summary:

```markdown
## TR1: <Description>
### Result: PASSED (with 1 warning)

| Step | Status | Details |
|------|--------|---------|
| Step 1: Navigate | PASSED | Account page loaded |
| Step 2: Open AI Panel | PASSED | Zuora AI panel visible |
| Step 3: Submit Prompt | PASS_WITH_WARNING | See Issue #1 |
| Step 4: Verify Flow | PASSED | Multi-turn context maintained |

### Issues Encountered
| # | Step | Issue | Classification | Action Taken | Outcome | Evidence |
|---|------|-------|---------------|-------------|---------|----------|
| 1 | Step 3 | Response took 45s | transient_delay | Waited longer | Warning | — |
```

Save to `execution/reports/{Feature}_TR{N}_report.md` using the same testmatrix `{Feature}` id (format in **Execution Report** above).

## Environment Configuration

### Config Access

Read `execution/config/test_config.yaml` for:

- `ui_base_url`: Base URL for the Zuora UI
- `ui_authentication.username`: Login username
- `ui_authentication.password`: Login password
- `test_data.*`: Pre-seeded test data references

### Environment Selection

Default: `staging` (from `default_environment` in config). Override via `TEST_ENVIRONMENT` env var.

### Multi-Tenant Support

Some tests run against specific tenants. The UI test doc's `environment_keys` field lists which config keys are needed. When `tenant_suffix` is specified, use the matching config section.
