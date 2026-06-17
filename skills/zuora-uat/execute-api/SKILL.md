---
name: zuora-uat-execute-api
description: Internal API pytest execution for one TR
---

# Execute API test (internal)

## Tenant resolution

```bash
GIT_ROOT=$(git rev-parse --show-toplevel)
eval "$(python3 "${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/scripts/tenant_resolve.py" \
  --git-root "$GIT_ROOT" --environment <environment> 2>&1 | grep '^export')"
export CLEANUP_DEBUG_FILES=false
```

Config paths: `<uat-root>/execution/config/` (default `<git-root>/uat/execution/config/`).

Ensure `$UAT_ROOT/execution/tests/test_utils/` has shipped helpers. Copy any **missing** files from `${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/tests/test_utils/` (at minimum `debug_utils.py`, `api_client.py`, `repo_paths.py`, `uat_root.py`).

## Run

```bash
source "$GIT_ROOT/.venv/bin/activate"
cd "$UAT_ROOT/execution"
python -m pytest "<resolved_api_script>" -v --tb=short \
  --junitxml=reports/junit_tr<n>.xml
```

Resolve script via `repo_paths.resolve_api_test_script_path(feature, tr_index)`.

## Outputs

- `execution/debugging/*.log` — for UI steps
- `execution/reports/junit*.xml`

## References

- `${CLAUDE_PLUGIN_ROOT}/references/uat-test/execution/docs/DEBUGGING_MECHANISM_GUIDE.md`
