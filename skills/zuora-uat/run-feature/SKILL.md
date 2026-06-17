---
name: zuora-uat-run-feature
description: Internal worker — verify gate + execute-api + execute-ui for one feature
---

# Run feature worker (internal)

**Inputs:** `feature`, optional `tr_filter`, `verify` (`auto`|`true`|`false`), `environment`, `max_fix_retries`.

## Startup (required, once per feature)

Ensure a canonical verification manifest exists before any TR work:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/scripts/uat_verification.py" ensure-manifest \
  --git-root "$GIT_ROOT" \
  --feature "<feature>"
# When tr_filter is set, append --tr N for each TR in scope
```

Resolve scenario dir: `$UAT_ROOT/execution/tests/test_scenarios/test_<feature>/` (via `repo_paths.resolve_feature_scenario_dir`).

## Per-TR verify decision

| `verify` | Behavior |
|----------|----------|
| `false` | Execute directly; no fix/review |
| `true` | Always run verify segment first |
| `auto` | Run verify when mark missing, `verified: false`, or `artifact_revision` stale |

Check stale marks:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/scripts/uat_verification.py" should-verify \
  --scenario-dir "<scenario_dir>" --tr <n> --git-root "$GIT_ROOT" --feature "<feature>"
```

Exit 0 → run verify; exit 1 → skip verify.

## Per TR in scope

1. **Verify gate** (when applicable) — `verify/SKILL.md`. On failure: skip execute for this TR.
2. **Execute API** — `execute-api/SKILL.md`
3. **Hybrid handoff (required after API pass)** — run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/scripts/hybrid_tr_prepare.py" \
  --git-root "$GIT_ROOT" \
  --feature "<feature>" \
  --tr <n> \
  --environment "<environment>"
```

| `execute_ui` | Action |
|--------------|--------|
| `true` | **MUST** run `execute-ui/SKILL.md` using `variables`, `ui_steps_path`, and `debug_log` from script output. Do not return worker JSON until UI completes or retries are exhausted. |
| `false` | Record skip reason in worker JSON (`execution.TRn.ui=skipped`, `execution.TRn.reason=<skip_reason>`). Call `record-ui-result` with `--status skipped --reason "<skip_reason>"`. |

4. **Record UI outcome (required for hybrid TRs)** — after UI pass/fail/skip:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/scripts/uat_verification.py" record-ui-result \
  --scenario-dir "<scenario_dir>" \
  --tr <n> \
  --status passed|failed|skipped \
  --evidence "<report_or_screenshot_path>" \
  --summary "<one-line outcome>"
```

5. On verify pass during run: update mark (`verified: true`, `artifact_revision`)

## Return contract (JSON only)

```json
{
  "feature": "<stem>",
  "tr_filter": ["TR1"],
  "status": "completed",
  "artifacts": {},
  "verification": { "TR1": { "verified": true, "artifact_revision": "abc123" } },
  "execution": {
    "TR1": { "api": "passed", "ui": "passed", "evidence": "execution/reports/tr1_account_page.md" }
  },
  "failures": []
}
```

Return **only** this summary to the parent orchestrator.
