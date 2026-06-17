---
name: zuora-uat-generate-api
description: Internal API pytest script generation from per-TR test design
---

# Generate API test script (internal)

Implements `execution/tests/test_scenarios/test_<feature>/test_<feature>_tr{n}_api.py` from `tr{n}_test_design.md`.

## Gap-fill

Skip when `force_overwrite=false` and `*_tr{n}_api.py` exists.

## Requirements

- One test method per TR (one debug log file per run)
- Class-based pytest with `@pytest.fixture(autouse=True)` setup/teardown
- `FEATURE_ID` = testmatrix feature string (stem of `design/testmatrix/<Feature>_TRs.md`)
- Before `create_debug_logger`, delete stale logs: `glob_debug_log_files(FEATURE_ID, "TR<n>")`
- `create_debug_logger(test_name="TR<n>_...", feature_id=FEATURE_ID, debug_dir="debugging", api_client=self.api_client)`
- Every API call: `self.debug_logger.log_request_response(step=..., request_data=..., response_data=...)`
- Include UI-needed IDs in `response_data` (`accountId`, `subscriptionNumber`, etc.)
- In `finally`: `self.debug_logger.cleanup_if_passed()` (preserves log when `CLEANUP_DEBUG_FILES=false`)
- Real API calls via `APIClient` (no mocks); use `tests/test_utils/debug_utils.py` from customer repo (copy missing files from `${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/tests/test_utils/`)
- Follow `${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/docs/E2E_TEST_IMPLEMENTATION_GUIDELINE.md`
- Follow `${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/docs/DEBUGGING_MECHANISM_GUIDE.md`

## MCP

`mcp__zuora-mcp__zuora_codegen` for request/response shapes. Search repo + guidelines before `ask_zuora`.

## Tenant

Generation is tenant-free. Scripts use `APIClient` which supports `environment=mcp` via env vars when no `test_config.yaml`.
