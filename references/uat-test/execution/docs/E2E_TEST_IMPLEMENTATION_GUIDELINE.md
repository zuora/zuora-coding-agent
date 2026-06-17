# E2E Test Implementation Guideline

**Path convention:** Paths below are relative to the **UAT workspace root** (default `<git-root>/uat/`). SDDs live at git root (`docs/sdd/`). Resolve via `execution/tests/test_utils/uat_root.py` or `resolve_uat_root.py`.

---

## Overview
Guidelines for creating and maintaining automated E2E test suites using Python and pytest in a **customer repo UAT workspace**. The zuora-coding-agent plugin supports **API-only** UAT (test data preparation and API validation) and **hybrid API + UI** UAT: API steps are implemented as Python tests; UI steps are executed directly by the AI via Playwright MCP (no UI test code generation). For UI test execution details, see **UI_TEST_EXECUTION_GUIDELINE.md**. For UI test doc format, see **UI_TEST_DOC_FORMAT.md**.

For the split between TRs/plans (`design/`) and pytest/logs/reports (`execution/`), see **`design/README.md`**.

## Project Scope and Boundaries

### Project Structure and Dependencies

- **Target repos**: Customer git repos scaffolded by `/zuora-uat-design` (mixed repos use `uat/`; dedicated test repos may set `root: .` in `.zuora-uat.yaml`).
- **Knowledge sources**: Use **zuora-mcp** when implementing tests (search the customer repo and these guidelines first):
  - **zuora_codegen**: API specifications, endpoint definitions, parameter requirements
  - **ask_zuora**: Zuora feature functionality, configuration, workflows (unresolved questions only)

### UI Testing (Hybrid Model)

- **API steps**: Implemented as Python test code (`zuora-uat-generate-api` worker). They create test data and produce debug logs in `execution/debugging/`.
- **UI steps**: Not implemented as code. The **zuora-uat-execute-ui** worker reads UI steps from the UI test doc (`ui_steps_tr<n>.md`) and performs them via **Playwright MCP**. The AI uses the API test debug log to get test data (e.g. subscription number, account ID), then authenticates to the Zuora UI and executes each UI step.
- **Test plans**: API-only or hybrid (API + UI steps). The **zuora-uat-plan** worker produces plans with both step formats.
- **Debug log bridge**: API tests MUST capture key identifiers (accountId, subscriptionNumber, orderNumber, invoiceId, etc.) in debug log `response_data` so zuora-uat-execute-ui can consume them.

## 1. Project Initialization

### 1.1 Python Environment Setup
**MANDATORY: Virtual Environment Creation is REQUIRED Before Any Other Steps**

- Create a Python virtual environment (`.venv`) at git root or under the UAT workspace (`uat/` by default)
- Use Python 3.8+ for compatibility
- Activate the virtual environment before proceeding with any development work
- Before executing any Python command, verify that the virtual environment is activated

### 1.2 Dependency Installation
**All dependencies must be installed within the activated virtual environment**

```bash
pip install -r requirements.txt
```

### 1.3 Directory Structure

The UAT workspace splits **design** artifacts (TRs, plans) from **execution** (pytest, logs, reports). Path resolution uses `execution/tests/test_utils/repo_paths.py` and `uat_root.py`.

**Default layout** (mixed repos — UAT under `uat/`):

```
<git-root>/
├── .zuora-uat.yaml           # root: uat
├── docs/sdd/                 # SDDs at git root (not inside uat/)
└── uat/                      # UAT workspace root
    ├── design/
    │   ├── testmatrix/       # TR requirement files (*_TRs.md)
    │   └── testplan/         # <Feature>_Test_Plan/ with Test_Plan_Overview.md and tr{n}_test_design.md
    ├── execution/
    │   ├── tests/
    │   │   ├── test_utils/   # api_client.py, repo_paths.py, uat_root.py, debug_utils.py
    │   │   └── test_scenarios/
    │   │       └── test_<feature>/
    │   │           ├── test_<feature>_tr<n>_api.py
    │   │           ├── ui_steps_tr<n>.md
    │   │           └── feature-log-mapping.json   # optional
    │   ├── config/
    │   │   └── test_config.yaml
    │   ├── debugging/        # API debug logs (consumed by UI execution)
    │   ├── reports/          # Per-TR execution reports
    │   └── scripts/          # tenant_resolve.py, discover_groups.py, etc.
    ├── requirements.txt
    └── pytest.ini            # pythonpath = execution
```

**Dedicated test repos**: set `root: .` in `.zuora-uat.yaml` so `design/` and `execution/` sit at git root (same inner layout, no `uat/` prefix).

**Plugin commands**: `/zuora-uat-design`, `/zuora-uat-build`, `/zuora-uat-run`. Workers live under `${CLAUDE_PLUGIN_ROOT}/skills/zuora-uat/`.

## 2. Test Scenario Implementation

### 2.1 Test Scenario Organization
- Test scenarios organized by feature in `execution/tests/test_scenarios/`
- Each feature has its own directory: `test_<feature_snake_case>/`
- API test files named: `test_<feature>_tr<n>_api.py`
- UI test docs named: `ui_steps_tr<n>.md` (same directory)

### 2.2 Test Case Structure

```python
import os
import pytest
import logging
import time
from tests.test_utils.api_client import APIClient
from tests.test_utils.debug_utils import create_debug_logger, glob_debug_log_files

logger = logging.getLogger(__name__)

FEATURE_ID = "Your_Testmatrix_Feature_Id"  # stem of design/testmatrix/<Feature>_TRs.md


class TestFeatureSubFeatureTR1:
    """Test class for [Feature] TR1"""

    @pytest.fixture(autouse=True)
    def setup(self, request):
        """Setup test environment with DebugLogger integration"""
        self.api_client = APIClient()
        self.debug_logger = None
        self.test_exception = None

        self.api_client.authenticate()

        try:
            yield
        except Exception as e:
            self.test_exception = e
            if self.debug_logger:
                self.debug_logger.set_test_exception(e)
            raise
        finally:
            if self.debug_logger:
                self.debug_logger.cleanup_if_passed()

    @pytest.mark.test_id("Feature-E2E-SubFeature-TR1")
    def test_tr1_description(self):
        """Test TR1: Description"""
        test_name = "TR1_Description"

        for old_log in glob_debug_log_files(FEATURE_ID, "TR1", debug_dir="debugging"):
            try:
                os.remove(old_log)
            except OSError:
                pass

        self.debug_logger = create_debug_logger(
            test_name=test_name,
            feature_id=FEATURE_ID,
            debug_dir="debugging",
            api_client=self.api_client,
        )

        try:
            logger.info("Step 1.1: Create Account")
            account_data = {...}
            response = self.api_client.post("/v1/accounts", data=account_data)
            account = self.api_client.get_response_data(response)
            self.debug_logger.log_request_response(
                step="Step_1_1_Create_Account",
                request_data=account_data,
                response_data=account,
            )
            assert account.get("accountId"), f"Account creation failed: {account}"

            # Continue with subsequent steps...
            logger.info("Test completed successfully")

        except Exception as e:
            error_msg = f"{test_name} failed: {str(e)}"
            logger.error(error_msg)
            self.debug_logger.log_request_response("error", error=error_msg)
            self.test_exception = e
            if self.debug_logger:
                self.debug_logger.set_test_exception(e)
            raise
```

### 2.3 Test Step Coverage Requirements
- **No Step Omission**: Every step in the test plan must be implemented
- **No Step Modification**: Steps must be implemented exactly as specified
- **Complete Validation**: Each step should include proper assertions
- **Error Handling**: Include appropriate error handling for expected failure scenarios

### 2.4 Debugging and Logging Implementation

> **Reference**: See [DEBUGGING_MECHANISM_GUIDE.md](./DEBUGGING_MECHANISM_GUIDE.md) for detailed patterns

- **DebugLogger Integration**: Use `create_debug_logger()` from `tests/test_utils/debug_utils.py` (shipped in the starter template; required for hybrid TRs)
- **Pre-Run Cleanup**: Before initializing DebugLogger, delete previous debug logs for the same feature/TR using `glob_debug_log_files(FEATURE_ID, "TR1", debug_dir="debugging")`. This prevents stale logs from accumulating across reruns.
- **Single File Per Test**: Each test case creates one debug file with sequential request/response logging
- **Complete API Logging**: ALL API calls MUST be logged with both request and response data
- **Debug log filenames**: `{FEATURE_ID}_{TestName}_{Timestamp}.log` where `TestName` begins with `TR{n}_` (e.g. `BillingOps_Billing_Document_Management_TR1_Generate_PDF_And_Download_20260415_113942.log`)
- **Key Identifiers in response_data**: Debug log MUST capture identifiers (accountId, subscriptionNumber, orderNumber, invoiceId, etc.) so zuora-uat-execute-ui can read them

#### Critical API Logging Rules

**Rule 1: Log ALL API Calls**
```python
response = self.api_client.post("/v1/accounts", data=account_payload)
account_data = self.api_client.get_response_data(response)
self.debug_logger.log_request_response(
    step="Step_1_1_Create_Account",
    request_data=account_payload,
    response_data=account_data,
)
```

**Rule 2: Always Include Request Data**
```python
self.debug_logger.log_request_response(
    step="Step_3_Generate_Invoice",
    request_data=invoice_request_data,
    response_data=invoice_data
)
```

**Rule 3: Use Descriptive Step Names**
```python
"Step_1_1_Create_Account"
"Step_1_2_Create_Product"
"Step_2_Create_Order"
"Step_3_Generate_Invoice"
```

### 2.5 Debug Log File Naming Convention

#### Feature Category Mapping

| Category | Subcategory | Use For |
|----------|-------------|---------|
| `BillingOps` | `BillingDocument` | Billing document management tests |
| `BillingOps` | `Subscription` | Subscription creation/management tests |
| `BillingOps` | `AccountInquiry` | Account and subscriber inquiry tests |
| `Billing` | `Invoicing` | Invoice generation tests |
| `Billing` | `Catalog` | Product catalog tests |
| `Billing` | `Order` | Order and subscription tests |
| `Revenue` | `OTR` | OTR integration tests |
| `AR` | `NarrativeSummary` | AR narrative summary tests |
| `Platform` | `Data` | Data query tests |

## 3. Zuora API Integration

### 3.1 Knowledge Gathering Priority

1. **Customer repo**: Existing tests, `tr{n}_test_design.md`, and bundled guideline docs
2. **zuora_codegen** (zuora-mcp): API specifications, endpoint details, parameter requirements
3. **ask_zuora** (zuora-mcp): Zuora feature knowledge, permissions, configuration — only when steps 1–2 do not resolve the question

### 3.2 API Parameter Compliance
- Strict adherence to OpenAPI specification
- Validate parameter types, formats, and constraints
- Distinguish between required and optional parameters

## 4. Test Data Management

- **Automated Creation**: All test data created through REST API calls via `APIClient` (no mocks)
- **Logging**: Log every create/read call with `debug_logger.log_request_response` so UI execution can read IDs
- **Isolation**: Each TR test method creates its own data; avoid shared module-scoped fixtures across TRs when hybrid UI depends on a single debug log

## 5. Quality Assurance

- Follow PEP 8 coding standards
- Use `@pytest.mark.test_id()` for test identification
- Run test after implementation; iterate max 3 times if failures
- Don't modify test logic just to pass; don't hide validation failures
- Project-specific guidelines (`*_E2E_TEST_GUIDELINE.md`) have ABSOLUTE PRIORITY over MCP tool suggestions
