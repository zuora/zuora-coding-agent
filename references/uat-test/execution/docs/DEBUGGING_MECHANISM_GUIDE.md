# E2E Test Framework - Debugging Mechanism Guide

**Path convention:** Paths below are relative to the **UAT workspace root** (default `<git-root>/uat/`).

## Overview

Comprehensive guide to the debugging mechanism for API-based test automation. The debugging system provides detailed logging for API requests/responses, with automatic cleanup and environment management. Debug logs serve as the bridge between API tests and UI test execution — the AI reads captured IDs from debug logs before driving the browser.

## Architecture Overview

1. **DebugLogger Class** — Core debugging utility in `tests/test_utils/debug_utils.py`
2. **Environment Configuration** — Configurable cleanup via `CLEANUP_DEBUG_FILES`
3. **Test Integration** — Seamless integration with pytest framework
4. **File Management** — Automatic log file creation and cleanup
5. **API Client Integration** — Request/response logging with URL capture

## Directory Structure

Runtime logs and traces live under **`execution/`**.

```
execution/
├── debugging/                     # API debug logs (consumed by UI execution)
│   ├── BillingOps_Billing_Document_Management_TR1_Generate_PDF_And_Download_20260415_113942.log
│   ├── Billing_Invoicing_TR1_Invoice_Generation_20260415_120000.log
│   └── AR_NarrativeSummary_TR1_Credit_Memo_Summary_20260415_130000.log
├── screenshots/                   # Legacy; UI evidence is recorded in per-TR reports (`## UI evidence`) via `browser_snapshot`
│   └── BillingOps_Billing_Document_Management_TR1/
│       └── final_result.png       # one end-of-TR capture per run
└── traces/                        # AI execution traces + captured vars JSON
    ├── billingops_billing_document_management.md
    └── billingops_billing_document_management.vars.json
```

## Core Component: DebugLogger

### Initialization

```python
import os
from tests.test_utils.debug_utils import create_debug_logger, glob_debug_log_files

FEATURE_ID = "BillingOps_Billing_Document_Management"  # stem of design/testmatrix/<Feature>_TRs.md

for path in glob_debug_log_files(FEATURE_ID, "TR1", debug_dir="debugging"):
    os.remove(path)

debug_logger = create_debug_logger(
    test_name="TR1_Generate_PDF_And_Download",
    feature_id=FEATURE_ID,
    debug_dir="debugging",
    api_client=api_client,
)
```

### Key Methods

#### `log_request_response(step, request_data, response_data, error, url)`
```python
debug_logger.log_request_response(
    step="Step_1_1_Create_Account",
    request_data=account_payload,
    response_data=account_response
)
```

#### `log_info(message)`
```python
debug_logger.log_info("Phase 1 complete. account_id=ABC, invoice_number=INV001")
```

#### `log_test_environment(account_number, config)`
```python
debug_logger.log_test_environment(self.account_number, self.config)
```

#### `log_test_summary(test_passed, error_message)`
```python
debug_logger.log_test_summary(test_passed=True, error_message=None)
```

#### `cleanup_if_passed()`
```python
debug_logger.cleanup_if_passed()
```

## File Naming Convention

**Format**: `{FEATURE_ID}_{TestName}_{YYYYMMDD_HHMMSS}.log` where `FEATURE_ID` matches the testmatrix feature string (same as `feature` in `feature-log-mapping.json` and report basenames), and `TestName` begins with `TR{n}_`.

**Examples**:
- `BillingOps_Billing_Document_Management_TR1_Generate_PDF_And_Download_20260415_113942.log`
- `BillingOps_Subscription_Lifecycle_Management_TR1_Cancel_Subscription_20260415_120000.log`
- `Billing_Invoicing_TR1_Invoice_Generation_20260415_120000.log` (legacy tests may still use older patterns until migrated)

## Log File Format

### Header
```
DEBUG LOG FOR TEST: TR1_Generate_PDF_And_Download
Timestamp: 2026-04-15T11:39:42.111516
Debug File: debugging/BillingOps_Billing_Document_Management_TR1_Generate_PDF_And_Download_20260415_113942.log
Cleanup Enabled: False
================================================================================
```

### Request/Response Entry
```
STEP: Step_1_1_Create_Account
Timestamp: 2026-04-15T11:39:43.222222
============================================================

REQUEST: POST https://rest.<environment>.zuora.com/v1/accounts

REQUEST DATA:
{
  "name": "AIDAILY_BillingDoc_Account_20260415113942",
  "currency": "USD",
  ...
}

RESPONSE DATA:
{
  "accountId": "8a90000000000000000000000000001",
  "accountNumber": "A00000001",
  "success": true
}

============================================================
```

### Test Summary
```
TEST SUMMARY
==================================================
Test: TR1_Generate_PDF_And_Download
Status: PASSED
Total Log Entries: 8
==================================================

LOG ENTRIES SUMMARY:
1. Step_1_1_Create_Account - Request data logged, Response data logged
2. Step_1_2_Create_Product - Request data logged, Response data logged
...
```

## Integration Pattern

### Standard Test Setup
```python
class TestBillingOpsBillingDocumentTR1:
    @pytest.fixture(autouse=True)
    def setup(self, request):
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

    @pytest.mark.test_id("BillingOps-E2E-BillingDocument-TR1")
    def test_tr1_generate_pdf_and_download(self):
        test_name = "TR1_Generate_PDF_And_Download"
        feature_id = "BillingOps_Billing_Document_Management"

        for old_log in glob_debug_log_files(feature_id, "TR1", debug_dir="debugging"):
            os.remove(old_log)

        self.debug_logger = create_debug_logger(
            test_name=test_name,
            feature_id=feature_id,
            debug_dir="debugging",
            api_client=self.api_client,
        )

        try:
            account_data = {...}
            response = self.api_client.post("/v1/accounts", data=account_data)
            account = self.api_client.get_response_data(response)
            self.debug_logger.log_request_response(
                step="Step_1_1_Create_Account",
                request_data=account_data,
                response_data=account,
            )
            # ...more steps...
        except Exception as e:
            error_msg = f"{test_name} failed: {str(e)}"
            logger.error(error_msg)
            self.debug_logger.log_request_response("error", error=error_msg)
            self.test_exception = e
            if self.debug_logger:
                self.debug_logger.set_test_exception(e)
            raise
```

## Critical API Logging Requirements

### Rule 1: Log ALL API Calls in Helper Methods
```python
def _create_account(self, payload):
    response = self.api_client.post("/v1/accounts", data=payload)
    account_data = self.api_client.get_response_data(response)
    self.debug_logger.log_request_response(
        "Step_1_1_Create_Account", request_data=payload, response_data=account_data
    )
    return account_data
```

### Rule 2: Always Include Request Data
```python
# CORRECT
self.debug_logger.log_request_response("Step_3_Generate_Invoice", request_data=invoice_request, response_data=invoice_data)

# WRONG — missing request data
self.debug_logger.log_request_response("Step_3_Generate_Invoice", response_data=invoice_data)
```

### Rule 3: Use Descriptive Step Names
```python
"Step_1_1_Create_Account"
"Step_1_2_Create_Product"
"Step_1_3_Create_Rate_Plan"
"Step_2_Create_Order_With_Subscription"
"Step_3_Execute_Bill_Run"
"Step_4_Verify_Invoice"
```

### Rule 4: Capture Key Identifiers
Response data MUST include identifiers that UI tests will need:
- `accountId`, `accountNumber`
- `subscriptionId`, `subscriptionNumber`
- `orderId`, `orderNumber`
- `invoiceId`, `invoiceNumber`
- `creditMemoId`, `creditMemoNumber`

## Environment Configuration

### Pre-Run Cleanup of Old Debug Logs

Before creating a new debug log, the test should remove previous debug logs for the same feature/TR to prevent stale files from accumulating. The **zuora-uat-execute-ui** worker reads only the most recent matching log, but old logs waste disk space and can cause confusion when browsing the directory.

**Pattern**: At the start of each test, before initializing DebugLogger, delete previous logs matching the same prefix:

```python
import os
from tests.test_utils.debug_utils import glob_debug_log_files

FEATURE_ID = "BillingOps_Billing_Document_Management"
for old_log in glob_debug_log_files(FEATURE_ID, "TR1", debug_dir="debugging"):
    os.remove(old_log)
```

This ensures `execution/debugging/` contains only the latest log per feature/TR.

### Post-Run Cleanup Control
```bash
# Enable post-run cleanup (default: false — debug logs preserved for UI execution)
export CLEANUP_DEBUG_FILES=true

# Disable post-run cleanup (preserve all files)
export CLEANUP_DEBUG_FILES=false
```

Post-run cleanup via `CLEANUP_DEBUG_FILES` is a separate concern: it controls whether a **passing** test deletes its own log after completion. Default is `false` because **zuora-uat-execute-ui** needs the log for UI step execution.

## Troubleshooting

### Missing Step 1 Logs
**Symptom**: Debug log starts at Step 2, missing test data creation logs.
**Cause**: Helper methods make API calls without logging.
**Fix**: Add `log_request_response()` for each API call in helper methods.

### Missing Request Data
**Symptom**: Log shows response data but no request data.
**Fix**: Always pass `request_data` parameter to `log_request_response()`.

### Verification Checklist
1. Every API call has a corresponding log entry
2. Both request and response data logged for each call
3. Step names are descriptive and sequential
4. Key identifiers (accountId, subscriptionNumber, etc.) are present in response data
5. Helper method API calls are individually logged
