---
name: zuora-uat-generate-feature
description: Internal worker — plan + generate-api + generate-ui + optional verify for one feature
---

# Generate feature worker (internal)

**Inputs:** `feature`, optional `tr_filter` (TR numbers), `force_overwrite`, `verify`, `environment`, `max_fix_retries`.

## Flow (per TR in scope)

1. **Plan** — `${CLAUDE_PLUGIN_ROOT}/skills/zuora-uat/plan/SKILL.md`
2. **API script** — `generate-api/SKILL.md` (gap-fill)
3. **UI doc** — `generate-ui/SKILL.md` when hybrid (gap-fill)
4. **UI placement check** (hybrid TRs only) — verify doc is in execution, not testplan (see below)
5. On artifact rewrite: clear verification mark for that TR:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/scripts/uat_verification.py" clear \
  --scenario-dir "$UAT_ROOT/execution/tests/test_scenarios/<folder>" --tr <n>
```

6. **Verify segment** when `verify=true` — `verify/SKILL.md` with `environment`
7. When `verify=false`: set `verified: false` for affected TRs (same `clear` command as step 5, per TR in scope)
8. **Required — finalize verification marks** before returning JSON:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/scripts/uat_verification.py" finalize-generate \
  --git-root "$GIT_ROOT" \
  --feature "<feature>" \
  --verify "<verify>"
# append --tr N when tr_filter is set
```

## UI placement check (after step 3, hybrid TRs)

Fail fast if `ui_steps_tr{n}.md` is missing from execution or present under testplan:

```bash
# A. Execution doc must exist
PYTHONPATH="$UAT_ROOT/execution/tests" python3 -c \
  "from test_utils.repo_paths import resolve_ui_steps_doc_path; resolve_ui_steps_doc_path('<feature>', '<TRn>')"

# B. No stray UI docs in testplan for this feature
test -z "$(find "$UAT_ROOT/design/testplan" -path '*<feature>*' -name 'ui_steps_tr*.md' -print)"
```

On failure: move misplaced file from testplan to the resolved execution path (or delete and rewrite), then retry the check once. If still failing, return worker JSON with a `failures` entry for that TR.

## TR list

- `tr_filter` null → all TRs from plan folder
- else → only listed TR numbers

## Verification manifest

Path: `execution/tests/test_scenarios/test_<feature>/.uat-verification.json`

Use `uat_verification.py` helpers from `${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/scripts/`.

## Return contract (JSON only)

```json
{
  "feature": "<stem>",
  "tr_filter": ["TR1"],
  "status": "completed",
  "artifacts": { "created": [], "skipped": [] },
  "verification": { "TR1": { "verified": true, "artifact_revision": "abc123" } },
  "execution": {},
  "failures": []
}
```

Return **only** this summary to the parent orchestrator.
