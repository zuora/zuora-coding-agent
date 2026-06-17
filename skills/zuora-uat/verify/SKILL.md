---
name: zuora-uat-verify
description: Internal verify segment execute-api → fix → review → execute-ui
---

# Verify segment (internal)

Shared by generate (`verify=true`) and run (verify gate).

## Sequence

1. **execute-api** — read `${CLAUDE_PLUGIN_ROOT}/skills/zuora-uat/execute-api/SKILL.md`
2. **fix** — on failure, loop up to `max_fix_retries` via `fix/SKILL.md`
3. **review** — `review/SKILL.md`
4. **execute-ui** — when UI doc exists and preconditions met (`execute-ui/SKILL.md`). After UI, call `record-ui-result` on the scenario manifest.

## On pass

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/scripts/uat_verification.py" set \
  --scenario-dir "<scenario_dir>" --tr <n> --verified true \
  --git-root "$GIT_ROOT" --feature "<feature>"
```

## On failure

Set `verified: false`, report issues, **stop downstream execute** for this TR.
