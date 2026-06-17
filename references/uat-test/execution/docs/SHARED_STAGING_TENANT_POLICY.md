# Shared staging tenant and Zuora AI verification policy

**Path convention:** Paths below are relative to the **UAT workspace root** (default `<git-root>/uat/`).

## Why this exists

Scheduled E2E runs use **one shared staging tenant**. Many suites seed data over time; Zuora AI answers **tenant-wide or window-wide** natural-language prompts against **all** data the queries can see—not only rows created in the current pytest run.

If tests treat **“only what this test seeded”** as the oracle for **unscoped** prompts (for example “top 10 renewals” or “summarize the next 90 days”), they encode **invalid expectations** and produce false failures or misleading triage.

## Role of API seeding

- **Purpose**: Ensure required facts **exist** in Zuora (accounts, invoices, payments, term dates) so the agent *can* return real evidence—not to define a **closed world** the agent must stay inside unless the **prompt or product** scopes to that set.
- **Debug logs**: May include **named-entity snapshots** (balances, IDs) for spot-checks. They may include **optional independent oracles** (ZOQL/REST for the **same scope as the NL prompt**, e.g. same date window) when numeric proof is required. They must not imply that **seed-only aggregates** are the mandatory pass bar for **tenant-wide** prompts.

## Core verification principle

Judge Zuora AI outputs on **correctness without unstated assumptions**:

1. **No imaginary data** — Account numbers, balances, payment IDs, counts, or dates that do not exist in Zuora or contradict captured API responses → treat as **FAILED** (fabrication or wrong record).
2. **No incorrect calculations** — Where the response claims totals, subtotals, percentages, or cross-foots, they must **reconcile** with the row set the agent presented (or with a clearly stated scope); internal math errors → **FAILED**.
3. **Validity for the actual data range** — For tenant-wide or time-window prompts, ask whether the answer is **consistent with what correct queries over the real tenant (and stated window) would return**, not whether it matches a **pytest aggregate built only from seed rows**. When automation needs numeric proof, derive expectations from **independent ground truth for that scope** (ZOQL/REST for the tenant or for **explicitly named** IDs in the prompt).

## Operational tiers (shorthand)

Use these when writing TRs, test plans, UI docs, and execution reports:

| Tier | When | What to assert |
|------|------|----------------|
| **A — Scoped prompt** | Prompt (or UI step) names account numbers, subscription numbers, or an explicit “only these accounts” cohort | **Exact** behavior and numbers **for that cohort** against API/ZOQL for those IDs. |
| **B — Unscoped tenant prompt** | Cross-account NL with no named cohort (rankings, rollups, “top N”, 90-day summaries) | **Structure**, **non-fabrication**, **internal consistency**; if totals must be proven, compare to a **tenant-wide or window-wide independent oracle**—not to seed-only crossfoot. Extra rows or months are acceptable if plausible for the tenant and not fabricated. |
| **C — Hard product failures** | Always serious | Fabrication; wrong entity when the prompt was scoped; arithmetic contradicting the agent’s own table; a failure signal **explicitly defined in the TR** as in-scope but **invisible** to the agent’s query path (product/tool gap). |

## Prompt vs expectation

- **Unscoped** NL (e.g. “top 10 renewals”, “next 90 days”) → Do **not** hard-fail solely because the answer includes **extra** accounts, **extra** calendar months, or **larger** totals than a seed-only baseline. Prefer **PASS_WITH_WARNING** with rationale, a **scoped follow-up** prompt to pin exact facts, or an **oracle-backed** numeric check.
- **Scoped** NL (named IDs or explicit cohort) → May require **exact** inclusion and reconciliation for that set.

## Anti-patterns

- **Seed-only baseline as oracle for tenant-wide prompts** — Fails good agent behavior when the tenant contains more (or larger) real data than the current test run created.
- **“Response must contain only seeded accounts”** for an unscoped cross-account prompt — Unrealistic on shared staging.
- **Treating PASS as “matches pytest JSON exactly”** when the TR intent is tenant insight—without an independent query for that scope.

## Positive pattern

Prefer wording like: the agent must surface the **seeded** entities where relevant, and **may** surface additional tenant rows; assertions check **no fabrication** and **consistency** with known facts. Example style: verification bullets that note the environment may include additional tenant rows beyond the seeded cohort (see **UI_TEST_DOC_FORMAT.md** — Shared staging tenant).

## Downstream references

Plugin skills under `${CLAUDE_PLUGIN_ROOT}/skills/zuora-uat/`:

- Design: `/zuora-uat-design`, `plan`
- Generate: `generate-feature`, `generate-api`, `generate-ui`, `plan`
- Execution: `execute-ui`, `execute-api`, `review`; docs `UI_TEST_EXECUTION_GUIDELINE.md`, `UI_TEST_DOC_FORMAT.md` (this directory)
