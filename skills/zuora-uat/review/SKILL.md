---
name: zuora-uat-review
description: Internal review aligning implementation with test plan and artifacts
---

# Review test case (internal)

After fix segment (or when verify already passes), align implementation with:

- `tr{n}_test_design.md`
- API script and debug log output
- `ui_steps_tr{n}.md` when hybrid

## Checks

- All plan steps covered in API script
- Debug log captures variables UI doc references
- UI steps match plan expectations and `${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/docs/SHARED_STAGING_TENANT_POLICY.md` (non-fabrication, correct math, valid query scope)
- No hardcoded tenant data that should come from API setup

Report gaps; if gaps remain after fix retries, verify segment fails.

## References

- `${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/docs/SHARED_STAGING_TENANT_POLICY.md`
- `${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/docs/UI_TEST_DOC_FORMAT.md` (verification phrasing for hybrid TRs)
